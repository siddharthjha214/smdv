function doPost(e) {
  var data = JSON.parse(e.postData.contents);
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  
  if (data.type === "new_video") {
    var sheet = ss.getSheetByName("Active_Videos"); 
    var values = sheet.getDataRange().getValues();
    var exists = false;
    for (var i = 1; i < values.length; i++) {
      if (values[i][3] === data.video_id) {
        exists = true;
        break;
      }
    }
    if (!exists) {
      sheet.appendRow([data.title, data.upload_time, "Active", data.video_id, data.url, "Pending", "", ""]);
      sortSheet(); // Automatically sort when a new video is added
    }
  }
  else if (data.type === "deleted_video") {
    var deletedSheet = ss.getSheetByName("Deleted/Private_Videos"); 
    // Column order: Title, Original Upload Time, Deleted Time, Status, Video ID, URL, Backup Video ID
    deletedSheet.appendRow([data.title, data.original_upload_time, data.deleted_time, data.status, data.video_id, data.url, data.backup_video_id]);

    // Remove the video from Active_Videos so the count stays accurate
    var activeSheet = ss.getSheetByName("Active_Videos");
    var activeValues = activeSheet.getDataRange().getValues();
    for (var i = activeValues.length - 1; i >= 1; i--) {
      if (activeValues[i][3] === data.video_id) {
        activeSheet.deleteRow(i + 1); // i+1 because sheet rows are 1-indexed
        break;
      }
    }
  }
  else if (data.type === "reset_backup") {
    var sheet = ss.getSheetByName("Active_Videos");
    var values = sheet.getDataRange().getValues();
    for (var i = 1; i < values.length; i++) {
      if (values[i][3] === data.video_id) {
        sheet.getRange(i + 1, 6).setValue("Pending");  // Column F: Backup Status
        sheet.getRange(i + 1, 7).setValue("");          // Column G: Backup Date
        sheet.getRange(i + 1, 8).setValue("");          // Column H: Backup Video ID
        break;
      }
    }
  }
  else if (data.type === "update_backup") {
    var sheet = ss.getSheetByName("Active_Videos");
    var values = sheet.getDataRange().getValues();
    for (var i = 1; i < values.length; i++) {
      if (values[i][3] === data.video_id) { // video_id is column D (index 3)
        // Update column F (Backup Status), G (Backup Date), H (Backup Video ID)
        sheet.getRange(i + 1, 6).setValue(data.backup_status);
        sheet.getRange(i + 1, 7).setValue("'" + data.backup_date); // Prepend ' to keep as string
        if (data.backup_video_id) {
          sheet.getRange(i + 1, 8).setValue(data.backup_video_id);
        }
      }
    }
    sortSheet(); // Automatically sort after status updates
  }
  
  return ContentService.createTextOutput("Success");
}

function doGet(e) {
  var action = e.parameter.action;
  
  if (action === "get_active_videos") {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName("Active_Videos");
    if (!sheet) return ContentService.createTextOutput(JSON.stringify({}));
    
    var values = sheet.getDataRange().getValues();
    var result = {};
    
    // Start at row 2 (index 1) assuming headers are in row 1
    for (var i = 1; i < values.length; i++) {
      var row = values[i];
      if (row[3]) { // video_id is column D (index 3)
        var existing = result[row[3]];
        if (existing && existing.backup_status === "Backed Up" && row[5] !== "Backed Up") {
          continue; // Keep the backed up version if there is a duplicate
        }
        var backup_date = row[6] || "";
        // If Google Sheets already converted it to Date before our fix, handle formatting
        if (backup_date instanceof Date) {
          // Send it back as ISO so python can handle it, or we could just format it
          // Actually, JSON.stringify will convert it to ISO string automatically
        }
        result[row[3]] = {
          "title": row[0],
          "upload_time": row[1],
          "status": row[2],
          "url": row[4],
          "backup_status": row[5] || "Pending",
          "backup_date": backup_date,
          "backup_video_id": row[7] || ""
        };
      }
    }
    
    // Add CORS headers to allow GitHub Pages frontend to fetch
    return ContentService.createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  }
  else if (action === "get_deleted_videos") {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName("Deleted/Private_Videos");
    if (!sheet) return ContentService.createTextOutput(JSON.stringify([]));
    
    var values = sheet.getDataRange().getValues();
    var result = [];
    
    // Start at row 2 assuming headers
    for (var i = 1; i < values.length; i++) {
      var row = values[i];
      if (row[4]) { // original video_id
        result.push({
          "title": row[0],
          "original_upload_time": row[1],
          "deleted_time": row[2],
          "status": row[3],
          "video_id": row[4],
          "url": row[5],
          "backup_video_id": row[6] || ""
        });
      }
    }
    
    return ContentService.createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function triggerGitHubAction() {
  var GITHUB_TOKEN = "PASTE_YOUR_GITHUB_TOKEN_HERE";
  var REPO_OWNER = "siddharthjha214";
  var REPO_NAME = "smdv";
  var WORKFLOW_ID = "monitor.yml";
  
  var url = "https://api.github.com/repos/" + REPO_OWNER + "/" + REPO_NAME + "/actions/workflows/" + WORKFLOW_ID + "/dispatches";
  
  var options = {
    "method": "POST",
    "headers": {
      "Authorization": "Bearer " + GITHUB_TOKEN,
      "Accept": "application/vnd.github.v3+json"
    },
    "payload": JSON.stringify({
      "ref": "main"
    }),
    "muteHttpExceptions": true
  };
  
  var response = UrlFetchApp.fetch(url, options);
  Logger.log(response.getContentText());
}

// ==========================================
// HELPERS FOR AUTOMATIC SORTING
// ==========================================

function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('YouTube Tracker')
      .addItem('Sort Videos by Date (Newest to Oldest)', 'sortSheet')
      .addToUi();
}

function parseDate(dateStr) {
  if (!dateStr) return new Date(0);
  var cleanStr = dateStr.toString().replace(" IST", "");
  var timestamp = Date.parse(cleanStr);
  return isNaN(timestamp) ? new Date(0) : new Date(timestamp);
}

function sortSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Active_Videos");
  if (!sheet) return;
  
  var lastRow = sheet.getLastRow();
  if (lastRow <= 2) return; 
  
  var range = sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn());
  var values = range.getValues();
  
  var seenIds = {};
  var uniqueValues = [];
  
  // 1. Filter out empty rows and deduplicate based on video_id (column D / index 3)
  for (var i = 0; i < values.length; i++) {
    var row = values[i];
    var videoId = row[3];
    if (videoId && videoId.toString().trim() !== "") {
      if (!seenIds[videoId]) {
        seenIds[videoId] = row;
        uniqueValues.push(row);
      } else {
        // If we see a duplicate, prioritize the one that is "Backed Up"
        var existingRow = seenIds[videoId];
        if (row[5] === "Backed Up" && existingRow[5] !== "Backed Up") {
          var idx = uniqueValues.indexOf(existingRow);
          if (idx !== -1) {
            uniqueValues[idx] = row;
            seenIds[videoId] = row;
          }
        }
      }
    }
  }
  
  // 2. Sort descending: newest date first, oldest at the bottom
  uniqueValues.sort(function(a, b) {
    var dateA = parseDate(a[1]);
    var dateB = parseDate(b[1]);
    return dateB - dateA;
  });
  
  // Clear the existing contents from row 2 onwards
  sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn()).clearContent();
  
  // Write the sorted and deduplicated values back starting from row 2
  sheet.getRange(2, 1, uniqueValues.length, sheet.getLastColumn()).setValues(uniqueValues);
}
