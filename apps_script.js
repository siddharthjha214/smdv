function doPost(e) {
  var data = JSON.parse(e.postData.contents);
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  
  if (data.type === "new_video") {
    // Column order: Title, Upload Time, Status, Video ID, URL, Backup Status, Backup Date, Backup Video ID
    var sheet = ss.getSheetByName("Active_Videos"); 
    sheet.appendRow([data.title, data.upload_time, "Active", data.video_id, data.url, "Pending", "", ""]);
  }
  else if (data.type === "deleted_video") {
    var sheet = ss.getSheetByName("Deleted/Private_Videos"); 
    // Column order: Title, Original Upload Time, Deleted Time, Status, Video ID, URL, Backup Video ID
    sheet.appendRow([data.title, data.original_upload_time, data.deleted_time, data.status, data.video_id, data.url, data.backup_video_id]);
  }
  else if (data.type === "update_backup") {
    var sheet = ss.getSheetByName("Active_Videos");
    var values = sheet.getDataRange().getValues();
    for (var i = 1; i < values.length; i++) {
      if (values[i][3] === data.video_id) { // video_id is column D (index 3)
        // Update column F (Backup Status), G (Backup Date), H (Backup Video ID)
        sheet.getRange(i + 1, 6).setValue(data.backup_status);
        sheet.getRange(i + 1, 7).setValue(data.backup_date);
        if (data.backup_video_id) {
          sheet.getRange(i + 1, 8).setValue(data.backup_video_id);
        }
        break;
      }
    }
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
        result[row[3]] = {
          "title": row[0],
          "upload_time": row[1],
          "status": row[2],
          "url": row[4],
          "backup_status": row[5] || "Pending",
          "backup_date": row[6] || "",
          "backup_video_id": row[7] || ""
        };
      }
    }
    
    // Add CORS headers to allow GitHub Pages frontend to fetch
    return ContentService.createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON)
      .setHeader("Access-Control-Allow-Origin", "*");
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
      .setMimeType(ContentService.MimeType.JSON)
      .setHeader("Access-Control-Allow-Origin", "*");
  }
}

function triggerGitHubAction() {
  var GITHUB_TOKEN = "PASTE_YOUR_NEW_ALARM_CLOCK_V2_TOKEN_HERE";
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
