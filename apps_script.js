function doPost(e) {
  var data = JSON.parse(e.postData.contents);
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var channel = data.channel || "main";
  var activeSheetName = "Active_Videos";
  var deletedSheetName = "Deleted/Private_Videos";
  if (channel === "spirituality") {
    activeSheetName = ss.getSheetByName("Sprituality_Active_Videos") ? "Sprituality_Active_Videos" : (ss.getSheetByName("Spirituality_Active_Videos") ? "Spirituality_Active_Videos" : "Sprituality_Active_Videos");
    deletedSheetName = ss.getSheetByName("Sprituality_Deleted_Videos") ? "Sprituality_Deleted_Videos" : (ss.getSheetByName("Spirituality_Deleted_Videos") ? "Spirituality_Deleted_Videos" : "Sprituality_Deleted_Videos");
  }

  if (data.type === "new_video") {
    var sheet = ss.getSheetByName(activeSheetName);
    if (!sheet) {
      sheet = ss.insertSheet(activeSheetName);
      sheet.appendRow(["Title", "Upload Time", "Status", "Video ID", "URL", "Backup Status", "Backup Date", "Backup Video ID", "Reupload Attempts"]);
    }
    var values = sheet.getDataRange().getValues();
    var exists = false;
    for (var i = 1; i < values.length; i++) {
      if (values[i][3] === data.video_id) {
        exists = true;
        break;
      }
    }
    if (!exists) {
      sheet.appendRow([data.title, data.upload_time, "Active", data.video_id, data.url, "Pending", "", "", 0]);
    }
  }
  else if (data.type === "update_date") {
    var sheet = ss.getSheetByName(activeSheetName);
    if (sheet) {
      var values = sheet.getDataRange().getValues();
      for (var i = 1; i < values.length; i++) {
        if (values[i][3] === data.video_id) {
          var currentDate = values[i][1] ? values[i][1].toString().trim() : "";
          if (currentDate === "" || currentDate === "Unknown") {
            sheet.getRange(i + 1, 2).setValue(data.upload_time);
          }
          break;
        }
      }
    }
  }
  else if (data.type === "bulk_restore") {
    var sheet = ss.getSheetByName(activeSheetName);
    if (!sheet) {
      sheet = ss.insertSheet(activeSheetName);
      sheet.appendRow(["Title", "Upload Time", "Status", "Video ID", "URL", "Backup Status", "Backup Date", "Backup Video ID", "Reupload Attempts"]);
    }
    var existingValues = sheet.getDataRange().getValues();
    var existingIds = {};
    for (var i = 1; i < existingValues.length; i++) {
      if (existingValues[i][3]) existingIds[existingValues[i][3]] = true;
    }
    var videos = data.videos;
    var rowsToInsert = [];
    var inserted = 0;
    for (var j = 0; j < videos.length; j++) {
      var v = videos[j];
      if (v.video_id && !existingIds[v.video_id]) {
        rowsToInsert.push([v.title, v.upload_time, "Active", v.video_id, v.url, "Pending", "", "", 0]);
        existingIds[v.video_id] = true;
        inserted++;
      }
    }
    if (rowsToInsert.length > 0) {
      sheet.getRange(sheet.getLastRow() + 1, 1, rowsToInsert.length, 9).setValues(rowsToInsert);
    }
    return ContentService.createTextOutput(JSON.stringify({ inserted: inserted }));
  }
  else if (data.type === "deleted_video") {
    var deletedSheet = ss.getSheetByName(deletedSheetName);
    if (!deletedSheet) {
      deletedSheet = ss.insertSheet(deletedSheetName);
      deletedSheet.appendRow(["Original Title", "Original Upload Date", "Deleted Detected Time", "Status", "Original Video ID", "Original URL", "Backup Video ID"]);
    }
    deletedSheet.appendRow([data.title, data.original_upload_time, data.deleted_time, data.status, data.video_id, data.url, data.backup_video_id]);

    var activeSheet = ss.getSheetByName(activeSheetName);
    if (activeSheet) {
      var activeValues = activeSheet.getDataRange().getValues();
      for (var i = activeValues.length - 1; i >= 1; i--) {
        if (activeValues[i][3] === data.video_id) {
          activeSheet.deleteRow(i + 1);
          break;
        }
      }
    }
  }
  else if (data.type === "reset_backup") {
    var sheet = ss.getSheetByName(activeSheetName);
    if (sheet) {
      var values = sheet.getDataRange().getValues();
      for (var i = 1; i < values.length; i++) {
        if (values[i][3] === data.video_id) {
          var attempts = (parseInt(values[i][8]) || 0) + 1;
          if (attempts >= 3) {
            sheet.getRange(i + 1, 6).setValue("YouTube Removed");
            sheet.getRange(i + 1, 7).setValue("");
            sheet.getRange(i + 1, 8).setValue("");
            sheet.getRange(i + 1, 9).setValue(attempts);
          } else {
            sheet.getRange(i + 1, 6).setValue("Pending");
            sheet.getRange(i + 1, 7).setValue("");
            sheet.getRange(i + 1, 8).setValue("");
            sheet.getRange(i + 1, 9).setValue(attempts);
          }
          break;
        }
      }
    }
  }
  else if (data.type === "update_backup") {
    var sheet = ss.getSheetByName(activeSheetName);
    if (sheet) {
      var values = sheet.getDataRange().getValues();
      for (var i = 1; i < values.length; i++) {
        if (values[i][3] === data.video_id) {
          sheet.getRange(i + 1, 6).setValue(data.backup_status);
          sheet.getRange(i + 1, 7).setValue("'" + data.backup_date);
          if (data.backup_video_id) {
            sheet.getRange(i + 1, 8).setValue(data.backup_video_id);
          }
          break;
        }
      }
    }
  }
  else if (data.type === "force_pending") {
    var sheet = ss.getSheetByName(activeSheetName);
    if (sheet) {
      var values = sheet.getDataRange().getValues();
      for (var i = 1; i < values.length; i++) {
        if (values[i][3] === data.video_id) {
          sheet.getRange(i + 1, 6).setValue("Pending");
          sheet.getRange(i + 1, 7).setValue("");
          sheet.getRange(i + 1, 8).setValue("");
          break;
        }
      }
    }
  }
  else if (data.type === "sort_sheet") {
    sortSheet(activeSheetName);
  }

  return ContentService.createTextOutput("Success");
}

function doGet(e) {
  var action = e.parameter.action;
  var channel = e.parameter.channel || "main";
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var activeSheetName = "Active_Videos";
  var deletedSheetName = "Deleted/Private_Videos";
  if (channel === "spirituality") {
    activeSheetName = ss.getSheetByName("Sprituality_Active_Videos") ? "Sprituality_Active_Videos" : (ss.getSheetByName("Spirituality_Active_Videos") ? "Spirituality_Active_Videos" : "Sprituality_Active_Videos");
    deletedSheetName = ss.getSheetByName("Sprituality_Deleted_Videos") ? "Sprituality_Deleted_Videos" : (ss.getSheetByName("Spirituality_Deleted_Videos") ? "Spirituality_Deleted_Videos" : "Sprituality_Deleted_Videos");
  }

  if (action === "get_active_videos") {
    var sheet = ss.getSheetByName(activeSheetName);
    if (!sheet) return ContentService.createTextOutput(JSON.stringify({})).setMimeType(ContentService.MimeType.JSON);

    var values = sheet.getDataRange().getValues();
    var result = {};

    for (var i = 1; i < values.length; i++) {
      var row = values[i];
      if (row[3]) {
        var existing = result[row[3]];
        if (existing && existing.backup_status === "Backed Up" && row[5] !== "Backed Up") {
          continue;
        }
        var backup_date = row[6] || "";
        result[row[3]] = {
          "title": row[0],
          "upload_time": row[1],
          "status": row[2],
          "url": row[4],
          "backup_status": row[5] || "Pending",
          "backup_date": backup_date,
          "backup_video_id": row[7] || "",
          "reupload_attempts": parseInt(row[8]) || 0
        };
      }
    }

    return ContentService.createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  }
  else if (action === "get_deleted_videos") {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(deletedSheetName);
    if (!sheet) return ContentService.createTextOutput(JSON.stringify([])).setMimeType(ContentService.MimeType.JSON);

    var values = sheet.getDataRange().getValues();
    var result = [];

    for (var i = 1; i < values.length; i++) {
      var row = values[i];
      if (row[4]) {
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

// ==========================================
// HELPERS FOR AUTOMATIC SORTING
// ==========================================

function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('YouTube Tracker')
    .addItem('Sort Main Channel Videos', 'sortMainSheet')
    .addItem('Sort Spirituality Videos', 'sortSpiritualitySheet')
    .addToUi();
}

function sortMainSheet() {
  sortSheet('Active_Videos');
}

function sortSpiritualitySheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheetName = ss.getSheetByName("Sprituality_Active_Videos") ? "Sprituality_Active_Videos" : "Spirituality_Active_Videos";
  sortSheet(sheetName);
}

function parseDate(dateStr) {
  if (!dateStr) return new Date(0);
  var cleanStr = dateStr.toString().replace(" IST", "");
  var timestamp = Date.parse(cleanStr);
  return isNaN(timestamp) ? new Date(0) : new Date(timestamp);
}

function sortSheet(sheetName) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(sheetName || "Active_Videos");
  if (!sheet) return;

  var lastRow = sheet.getLastRow();
  if (lastRow <= 2) return;

  var range = sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn());
  var values = range.getValues();

  var seenIds = {};
  var uniqueValues = [];

  for (var i = 0; i < values.length; i++) {
    var row = values[i];
    var videoId = row[3];
    if (videoId && videoId.toString().trim() !== "") {
      if (!seenIds[videoId]) {
        seenIds[videoId] = row;
        uniqueValues.push(row);
      } else {
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

  uniqueValues.sort(function (a, b) {
    var dateA = parseDate(a[1]);
    var dateB = parseDate(b[1]);
    return dateB - dateA;
  });

  if (uniqueValues.length > 0) {
    sheet.getRange(2, 1, uniqueValues.length, sheet.getLastColumn()).setValues(uniqueValues);
    var leftoverRows = (lastRow - 1) - uniqueValues.length;
    if (leftoverRows > 0) {
      sheet.getRange(2 + uniqueValues.length, 1, leftoverRows, sheet.getLastColumn()).clearContent();
    }
  }
}
