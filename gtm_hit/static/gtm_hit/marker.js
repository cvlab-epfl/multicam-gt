var rectsID = [];
var boxes = {};
var chosen_rect;
var prev_chosen_identity;
var tracklet;
var toggleTrackletClick = true;

var imgArray = [];
// var arrArray = [];
var validation = {};
var identities = {};
var personID = 0;
var cameras = 7;
var camName = '';
var loadcount = 0;
var zoomOn = false;
var toggle_cuboid = true;
var toggle_unselected = true;
var frame_str = '0';
// var cameraPaths = [];
// var activeCameras = [];
// var workerID = 0;
// var dset_name = '';
let selectedBoxes = [];

var undistort_frames_path ='';
var zoomratio = [];
var rotation = [50, 230, 150, 75, 265, 340, 80];
// var bounds = [[0, 396, 1193, 180, 1883, 228, 1750, 1080], [0, 344, 1467, 77, 1920, 82, -1, -1],
// [97, 1080, 73, 273, 864, 202, 1920, 362], [0, 444, 1920, 261, -1, -1, -1, -1],
// [0, 435, 1920, 403, -1, -1, -1, -1], [0, 243, 29, 203, 656, 191, 1920, 442],
// [0, 244, 1920, 162, -1, -1, -1, -1]];
// var toggle_ground;
// var toggle_orientation;
var to_label = 12100;

let mouseDown = false;
let selectedBox = null;
var unsavedChanges = false;
var boxesLoaded = true;

// Global state to track transformations
var zoomState = [];


// let activeCameras = Array.from({length: cameraPaths.length}, (_, i) => i + 1); // Initially all cameras active

function initializeCameraMenu() {
  const menu = document.getElementById('cameraMenu');
  
  const header = document.createElement('li');
  header.className = 'dropdown-header';
  header.textContent = 'Toggle Cameras';
  menu.appendChild(header);

  const divider = document.createElement('li');
  divider.className = 'divider';
  menu.appendChild(divider);

  // Add Unselect All button
  const unselectAll = document.createElement('li');
  const unselectLink = document.createElement('a');
  unselectLink.href = '#';
  unselectLink.textContent = 'Unselect All';
  unselectLink.onclick = (e) => {
    // e.preventDefault();
    // First update all checkboxes
    cameraPaths.forEach(camName => {
      
        const checkbox = document.getElementById(`checkbox${camName}`);
        
        if (checkbox.checked) {  // Only toggle if currently checked
            // console.log(checkbox.checked);
            // checkbox.checked = false;
            // console.log(checkbox.checked);
            toggleCamera(camName);
        }
    });
  };

  unselectAll.appendChild(unselectLink);
  menu.appendChild(unselectAll);

  // Add another divider
  const divider2 = document.createElement('li');
  divider2.className = 'divider';
  menu.appendChild(divider2);

  cameraPaths.forEach((camName, index) => {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = '#';
      a.innerHTML = `<input type="checkbox" id="checkbox${camName}" checked> ${camName}`;
      a.onclick = (e) => {
          e.preventDefault();
          toggleCamera(camName);
      };
      li.appendChild(a);
      menu.appendChild(li);
  });

  document.getElementById('merge-boxes').addEventListener('click', handleMergeBoxes);
}


// function initializeCameraMenu() {
//     const menu = document.getElementById('cameraMenu');
    
//     const header = document.createElement('li');
//     header.className = 'dropdown-header';
//     header.textContent = 'Toggle Cameras';
//     menu.appendChild(header);
    
//     const divider = document.createElement('li');
//     divider.className = 'divider';
//     menu.appendChild(divider);
    
//     cameraPaths.forEach((camName, index) => {
//         const li = document.createElement('li');
//         const a = document.createElement('a');
//         a.href = '#';
//         a.innerHTML = `<input type="checkbox" id="checkbox${camName}" checked> ${camName}`;
//         a.onclick = (e) => {
//             e.preventDefault();
//             toggleCamera(camName);
//         };
//         li.appendChild(a);
//         menu.appendChild(li);
//     });
//     document.getElementById('merge-boxes').addEventListener('click', handleMergeBoxes);
    
  
// }
function toggleCamera(camName) {
  const checkbox = document.getElementById(`checkbox${camName}`);
  const wrapper = document.getElementById(`canv${camName}`).parentElement;
  
  if (checkbox && wrapper) {
      if (checkbox.checked) {
          checkbox.checked = false;
          wrapper.style.display = 'none';
          activeCameras = activeCameras.filter(id => id !== camName);
      } else {
          checkbox.checked = true;
          wrapper.style.display = 'block';
          activeCameras.push(camName);
      }
      updateCameraGrid();
  }
}

function updateCameraGrid() {
    const container = document.getElementById('cameraContainer');
    const numActive = activeCameras.length;
    
    // Update grid layout based on number of active cameras
    container.style.gridTemplateColumns = `repeat(${Math.min(Math.ceil(Math.sqrt(numActive)), 2)}, 1fr)`;
}

// Initialize the application
$(document).ready(function() {
  activeCameras = cameraPaths; // Assuming cameraPaths is defined globally
  initializeCameraMenu();
  updateCameraGrid();

  // Initialize zoomState dynamically based on the number of cameras
  updateZoomState();
});

// Function to initialize or update zoomState
function updateZoomState() {
  zoomState = Array.from({ length: nb_cams }, () => ({ scale: 1, translateX: 0, translateY: 0 }));

  console.log('Zoom State initialized:', zoomState, "for nb_cams:", nb_cams);
}

window.onload = function () {
  // toggle_ground = true;
  // toggle_orientation = false;

  // Initial AJAX request to populate frameStrs before loading images
  $.ajax({
    method: "POST",
    url: 'changeframe',
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      order: 'next',
      frameID: frame_str,
      incr: 0,
      workerID: workerID,
      datasetName: dset_name

    },
    dataType: "json",
    success: function (msg) {
      frameStrs = msg['frame_strs'];
      nblabeled = msg['nblabeled'];

      if (nblabeled >= to_label) {
        var button = document.getElementById("changeF");
        button.href = "/gtm_hit/" + dset_name + "/" + workerID + "/processFrame";
        button.text = "Finish";
      }

      // if (nblabeled > 0) {
        load();
      // }

      // Proceed with image loading after frameStrs has been populated
      // camName = cameraPaths.substring(2, cameraPaths.length - 2).split("', '");

      cameraPaths.forEach((camName, index) => {
        boxes[index] = {};
        imgArray[index] = new Image();
        imgArray[index].id = camName;
        imgArray[index].onload = function () {
          var c = document.getElementById("canv" + this.id);
          if (!c) {
            console.error("Canvas with ID canv" + this.id + " not found.");
            return;
          }
          var ctx = c.getContext('2d');
          ctx.drawImage(this, 0, 0);
      

          c.addEventListener('contextmenu', mainClick, false);
          c.addEventListener("mousedown", onMouseDown);
          c.addEventListener("mousemove", onMouseMove);
          c.addEventListener("mouseup", onMouseUp);
          c.addEventListener("click", drawDot);
          

          loadcount++;
          if (loadcount == nb_cams) {
            $("#loader").hide();
          }
          update();
        };

        loadcount = 0;
        $("#loader").show();

        if (useUndistorted == "True") undistort_frames_path = "undistorted_";

        imgArray[index].src = frameStrs[camName];//'/static/gtm_hit/dset/' + dset_name + '/' + undistort_frames_path + 'frames/' + camName + '/' + frameStrs[camName];
      })

      // // Load the top view after initial setup
      // var topview = new Image();
      // topview.id = "topviewimg";
      // topview.onload = function () {
      //   var c = document.getElementById("topview" + this.id);
      //   var ctx = c.getContext('2d');
      //   ctx.drawImage(this, 0, 0);
      // };
      // topview.src = '/static/gtm_hit/dset/scout/NewarkPennTopView2.tif';

    }
  });

  // Additional key bindings
  $(document).bind('keydown', "4", backSpace); // num 4
  $(document).bind('keydown', "a", leftLarge); // left
  $(document).bind('keydown', "d", rightLarge); // right
  $(document).bind('keydown', "w", upLarge); // up
  $(document).bind('keydown', "s", downLarge); // down
  $(document).bind('keydown', "ctrl+a", left); // a
  $(document).bind('keydown', "ctrl+d", right); // d
  $(document).bind('keydown', "ctrl+w", up); // w
  $(document).bind('keydown', "ctrl+s", down); // s
  // $(document).bind('keydown', "i", increaseHeight);
  // $(document).bind('keydown', "k", decreaseHeight);
  // $(document).bind('keydown', "o", increaseWidth);
  // $(document).bind('keydown', "u", decreaseWidth);
  // $(document).bind('keydown', "l", increaseLength);
  // $(document).bind('keydown', "j", decreaseLength);
  // $(document).bind('keydown', "e", rotateCW);
  // $(document).bind('keydown', "q", rotateCCW);
  // $(document).bind('keydown', "tab", tab);
  // $(document).bind('keydown', "space", space);
  // $(document).bind("keydown", "v", validate);
  $(document).bind("keydown", "z", zoomControl); // f
  // $(document).bind("keydown", "g", toggleGround);
  $(document).bind("keydown", "c", toggleCuboid); // c
  $(document).bind("keydown", "r", toggleUnselected); // h
  $(document).bind("keydown", "q", keyPrevFrame); // n
  $(document).bind("keydown", "e", keyNextFrame); // m
  $(document).bind("keydown", "ctrl+q", keyPrevFrame); // n
  $(document).bind("keydown", "ctrl+e", keyNextFrame); // m
  // $(document).bind("keydown", "b", toggleOrientation);
  $(document).bind("keydown", "f", save); // ctrl+s
  $(document).bind("keydown", "ctrl+f", save); // ctrl+s
  $(document).bind("keydown", "1", copyPrevOrNext); // ,
  $(document).bind("keydown", "x", splitAtCurrentFrame); // x
  $(document).bind("keydown", "v", autoAlignCurrent); // v
  // add copy button
  

  $("#pID").bind("keydown", "return", changeID);
  $("#pID").val(-1);
  $("#pHeight").val(-1);
  $("#pWidth").val(-1);
};

function onMouseDown(event) {
  if (event.button !== 0) return;
  
  let tracklet = [];
  mouseDown = true;
  const { offsetX, offsetY } = event;
  // Get canvas context to access current transform state
  const ctx = this.getContext('2d');
  const transform = ctx.getTransform();
  // First convert the DOM event coordinates to "canvas coordinates"
  const canvasX = offsetX * (frame_size[0] / this.clientWidth);
  const canvasY = offsetY * (frame_size[1] / this.clientHeight);
  // Now invert the current zoom/pan transform so that we recover the original image coordinate
  const invTransform = transform.inverse();
  const origPoint = invTransform.transformPoint(new DOMPoint(canvasX, canvasY));
  var mousex = Math.round(origPoint.x);
  var mousey = Math.round(origPoint.y);
  // console.log('Clicked on: ', event.target.id)
  // Get the canvas index from the canvas id
  const canvasIndex = cameraPaths.indexOf(event.target.id.replace('canv', '',)); //parseInt(event.target.id.slice(4)) - 1;
  // console.log('Mouse coordinates:', {mousex, mousey});
  // console.log('Canvas index:', canvasIndex);

  // Check if any bounding box is selected
  let threshold = 10 / zoomState[canvasIndex].scale;
  let minDist = Infinity;
  let closestBox = null;
  let isBasePoint = false;

  // Find the closest point among all boxes
  for (const [personID, rectID] of Object.entries(rectsID)) {
    const pid = identities[rectID];
    const box = boxes[canvasIndex][pid];
    if (!box) {
      console.log(`Box for pid ${pid} is not defined.`);
      continue;
    }
  
    if (!box.cuboid || box.cuboid.length == 0) continue;
    
    let base_point = box.cuboid[8];
    let baseX = base_point[0];
    let baseY = base_point[1];
    
    // Calculate distances to both points
    const distToBase = Math.sqrt(Math.pow(mousex - baseX, 2) + Math.pow(mousey - baseY, 2));
    const distToMid = Math.sqrt(Math.pow(mousex - box.xMid, 2) + Math.pow(mousey - box.y1, 2));
    
    // Update if this is the closest point so far
    if (distToBase <= threshold && distToBase < minDist) {
      minDist = distToBase;
      closestBox = { rectID, pid, box };
      isBasePoint = true;
    }
    if (distToMid <= threshold && distToMid < minDist) {
      minDist = distToMid;
      closestBox = { rectID, pid, box };
      isBasePoint = false;
    }
  }

  // Handle the closest box if one was found
  if (closestBox) {
    chosen_rect = rectsID.indexOf(closestBox.rectID);
    
    if (isBasePoint) {
      // Select for drag if base point was closest
      selectedBox = { rectID: closestBox.rectID, canvasIndex };
    } else {
      // Regular selection if mid point was closest
      console.log('Selected box:', closestBox);
      console.log('Selected boxes:', selectedBoxes);

      if (event.shiftKey) {
        if (selectedBoxes.length < 2) {
          selectedBoxes.push(closestBox);
        }
        if (selectedBoxes.length === 2) {
          document.getElementById('merge-boxes').disabled = false;
        }
        update();
        return;
      }
      
      selectedBoxes = [];
      update();
      getTracklet();
      displayCrops(frame_str, closestBox.pid, canvasIndex);
      timeview_canv_idx = canvasIndex;
    }
  }
  if (toggleTrackletClick) {
    // Check tracklet change frame
    const dataList = tracklet[canvasIndex];
    if (dataList==undefined) return;
    for (let i = 0; i < dataList.length; i++) {
      var x = dataList[i][1][0];
      var y  = dataList[i][1][1];
      if (
        mousex >= x - threshold &&
        mousex <= x + threshold &&
        mousey >= y - threshold &&
        mousey <= y + threshold
      ) {
        if (dataList[i][0] < frame_str) changeFrame("prev", frame_str-dataList[i][0])
        else
        changeFrame("next", dataList[i][0]-frame_str)
      }
    }
  }
}


// document.getElementById('merge-boxes').addEventListener('click', () => {
//   if (selectedBoxes.length === 2) {
//     personID1 = selectedBoxes[0].personID;
//     personID2 = selectedBoxes[1].personID;

//     $.ajax({
//       method: "POST",
//       url: 'merge',
//       data: {
//           csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
//           personID1: personID1,
//           personID2: personID2,
//           workerID: workerID,
//           datasetName: dset_name
//       },
//       success: function (msg) {
//         console.log(msg);
//         unsavedChanges = false;
//         load();
//         $("#unsaved").html("All changes saved.");
      
//       selectedBoxes.forEach(box => {
//           box.element.classList.remove('selected-for-merge');
//       });
//       selectedBoxes = [];
//       document.getElementById('merge-boxes').disabled = true;
//   }
// })}});

// document.getElementById('merge-boxes').addEventListener('click', () => {
//   if (selectedBoxes.length === 2) {
//       const personID1 = selectedBoxes[0].person_id;  // Match Django model field name
//       const personID2 = selectedBoxes[1].person_id;
      
//       // Add frame context
//       const frameID = parseInt(frame_str);

//       $.ajax({
//           method: "POST",
//           url: 'merge',
//           data: {
//               csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
//               personID1: personID1,
//               personID2: personID2,
//               frameID: frameID,  // Include current frame context
//               workerID: workerID,
//               datasetName: dset_name
//           },
//           success: function(msg) {
//               console.log('Merge response:', msg);
//               unsavedChanges = false;
              
//               // Clear selections before reloading
//               selectedBoxes.forEach(box => {
//                   box.element.classList.remove('selected-for-merge');
//               });
//               selectedBoxes = [];
//               document.getElementById('merge-boxes').disabled = true;
              
//               // Reload annotations
//               load();
//               $("#unsaved").html("All changes saved.");
//           },
//           error: function(xhr, status, error) {
//               console.error('Merge failed:', error);
//               $("#unsaved").html("Error during merge operation.");
//           }
//       });
//   }
// });

function handleMergeBoxes() {
  if (selectedBoxes.length === 2) {
      const personID1 = selectedBoxes[0].pid;
      const personID2 = selectedBoxes[1].pid;
      const frameID = parseInt(frame_str);

      $.ajax({
          method: "POST",
          url: 'merge',
          data: {
              csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
              personID1: personID1,
              personID2: personID2,
              workerID: workerID,
              datasetName: dset_name
          },
          success: function(msg) {
              console.log('Merge response:', msg);
              unsavedChanges = false;
              
              selectedBoxes = [];
              document.getElementById('merge-boxes').disabled = true;
              
              // Reload annotations
              load();
              $("#unsaved").html("All changes saved.");
          },
          error: function(xhr, status, error) {
              console.error('Merge failed:', error);
              $("#unsaved").html("Error during merge operation.");
          }
      });
  }
}




function onMouseMove(event) {
  if (!mouseDown || !selectedBox) return;
  const { offsetX, offsetY } = event;
  // Get canvas context to access current transform state
  const ctx = this.getContext('2d');
  const transform = ctx.getTransform();
  // First convert the DOM event coordinates to "canvas coordinates"
  const canvasX = offsetX * (frame_size[0] / this.clientWidth);
  const canvasY = offsetY * (frame_size[1] / this.clientHeight);
  // Now invert the current zoom/pan transform so that we recover the original image coordinate
  const invTransform = transform.inverse();
  const origPoint = invTransform.transformPoint(new DOMPoint(canvasX, canvasY));
  var mousex = Math.round(origPoint.x);
  var mousey = Math.round(origPoint.y);
  
  const { rectID, _ } = selectedBox;
  const canvasIndex = cameraPaths.indexOf(event.target.id.replace('canv', '',));
  const pid = identities[rectID];
  const box = boxes[canvasIndex][pid];
  let base_point = box.cuboid[8];
  let baseX = base_point[0];
  let baseY = base_point[1];

  const dx = mousex - baseX;
  const dy = mousey - baseY;
  // Update the box coordinates
  let newcuboid = [];
  for (let i = 0; i < 9; i++) {
    let newpoint = [box.cuboid[i][0] + dx, box.cuboid[i][1] + dy];
    newcuboid.push(newpoint);
  }
  boxes[canvasIndex][pid] = {
    ...box,
    x1: box.x1 + dx,
    x2: box.x2 + dx,
    y1: box.y1 + dy,
    y2: box.y2 + dy,
    xMid: box.xMid + dx,
    cuboid: newcuboid
  };
  update();
}

function getFrameStrs() {
  $.ajax({
    method: "POST",
    url: 'changeframe',
    data: {
        csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
        order: order,
        frameID: frame_str,
        incr: 0,
        workerID: workerID,
        datasetName: dset_name
    },
    dataType: "json",
    success: function (msg) {
        frame_str = msg['frame'];
        nblabeled = msg['nblabeled'];
        frameStrs = msg['frame_strs']
        
        
        // if (useUndistorted=="True") undistort_frames_path="undistorted_"
        // for (var i = 0; i < nb_cams; i++) {
        //     imgArray[i].src = '/static/gtm_hit/dset/'+dset_name+'/'+undistort_frames_path+'frames/' + camName[i] + '/' + frameStrs[camName[i]];
        //     console.log(imgArray[i].src)
        // }
    }
})}

// function onMouseUp() {
//   if (!mouseDown || !selectedBox) return;
//   const { rectID, canvasIndex } = selectedBox;
//   const pid = identities[rectID];
//   const box = boxes[canvasIndex][pid];
//   mouseDown = false;

//   $.ajax({
//     method: "POST",
//     url: "click",
//     data: {
//       csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
//       x: box.xMid,
//       y: box.y2,
//       rotation_theta: box.rotation_theta,
//       object_size: box.object_size,
//       canv: this.id,
//       person_id: pid,
//       workerID: workerID,
//       datasetName: dset_name,
//     },
//     dataType: "json",
//     success: function (msg) {
//       var newrectid = msg[0].rectangleID;
//       var indof = rectsID.indexOf(newrectid);
//       if (indof == -1) {
//         const { rectID, canvasIndex } = selectedBox;
//         //save the new rectangle
//         const pid = identities[rectID];
//         const box = boxes[canvasIndex][pid];
//         saveRect(msg, pid);
//         //reassign the identity to the new rectangle
//         identities[newrectid] = pid;
//         delete identities[rectID];

//         // reassign the rectangle to the new identity
//         rectsID[rectsID.indexOf(rectID)] = newrectid;

//       } else {
//         chosen_rect = indof;
//       }
//       update();
//       selectedBox = null;
//     }
//   });
// }

function splitAtCurrentFrame(event) {

}

function onMouseUp(event) {
  if (!mouseDown || !selectedBox) return;
  
  const { offsetX, offsetY } = event;
  const ctx = this.getContext('2d');
  const transform = ctx.getTransform();
  const canvasX = offsetX * (frame_size[0] / this.clientWidth);
  const canvasY = offsetY * (frame_size[1] / this.clientHeight);
  const invTransform = transform.inverse();
  const origPoint = invTransform.transformPoint(new DOMPoint(canvasX, canvasY));
  var xCorr = Math.round(origPoint.x);
  var yCorr = Math.round(origPoint.y);
  
  const { rectID, canvasIndex } = selectedBox;
  const pid = identities[rectID];
  const box = boxes[canvasIndex][pid];
  mouseDown = false;

  $.ajax({
      method: "POST",
      url: "click",
      data: {
          csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
          x: xCorr,
          y: yCorr,
          rotation_theta: box.rotation_theta,
          object_size: box.object_size,
          frameID: frame_str,
          canv: this.id,
          person_id: pid,
          workerID: workerID,
          datasetName: dset_name,
      },
      dataType: "json",
      success: function (msg) {
        var newrectid = msg[0].rectangleID;
        var indof = rectsID.indexOf(newrectid);
        if (indof == -1) {
          const { rectID, canvasIndex } = selectedBox;
          //save the new rectangle
          const pid = identities[rectID];
          const box = boxes[canvasIndex][pid];
          saveRect(msg, pid);
          //reassign the identity to the new rectangle
          identities[newrectid] = pid;
          delete identities[rectID];
  
          // reassign the rectangle to the new identity
          rectsID[rectsID.indexOf(rectID)] = newrectid;
  
        } else {
          chosen_rect = indof;
        }
        update();
        selectedBox = null;
      }
  });
}


function mainClick(e) {
  e.preventDefault();
  const { offsetX, offsetY } = e;
  // Get canvas context to access current transform state
  const ctx = this.getContext('2d');
  const transform = ctx.getTransform();
  console.log("Transform:", frame_size);
  // First convert the DOM event coordinates to "canvas coordinates"
  const canvasX = offsetX * (frame_size[0] / this.clientWidth);
  const canvasY = offsetY * (frame_size[1] / this.clientHeight);

  console.log("Canvas coords:", canvasX, canvasY);
  // Now invert the current zoom/pan transform so that we recover the original image coordinate.
  const invTransform = transform.inverse();
  const origPoint = invTransform.transformPoint(new DOMPoint(canvasX, canvasY));

  console.log("Original image point:", origPoint);
  var xCorr = Math.round(origPoint.x);
  var yCorr = Math.round(origPoint.y);

  var pid = identities[rectsID[chosen_rect]];
  if (e.altKey) {
    var pid = "";
  }
  // let box = boxes[0][pid];
  // if (!box) return;
  // box["personID"] = pid;
  // if (zoomOn)
  //   zoomOut();
  //post

  if (e.ctrlKey) {
    autoalign = "true";
  } else {
    autoalign = "false";
  }

  $.ajax({
    method: "POST",
    url: "click",
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      x: xCorr,
      y: yCorr,
      frameID: frame_str,
      autoalign: autoalign,
      canv: this.id.replace('canv', ''),
      workerID: workerID,
      datasetName: dset_name,
      person_id: pid
    },
    dataType: "json",
    success: function (msg) {
      var rid = msg[0].rectangleID;
      var indof = rectsID.indexOf(rid);
      if (indof == -1) {
        rectsID.push(rid);
        chosen_rect = rectsID.length - 1;
        const personID = msg[0].personID;
        identities[rid] = personID;
        validation[personID] = true;
      } else {
        chosen_rect = indof;
      }
      saveRect(msg, msg[0].personID);
      update();
    }
  });
}

function getTracklet(e) {
  if(e)
  e.preventDefault();
  
  var pid = identities[rectsID[chosen_rect]];
  $.ajax({
    method: "POST",
    url: "tracklet",
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      personID: pid,
      frameID: parseInt(frame_str),
      workerID: workerID,
      datasetName: dset_name
    },
    dataType: "json",
    success: function (msg) {
      tracklet = msg;
      for (var i = 0; i < nb_cams; i++) {
        var c = document.getElementById("canv" + cameraPaths[i]);
        var ctx = c.getContext("2d");
        
        // Get current transform scale to adjust sizes
        const scale = ctx.getTransform().a;
        
        ctx.strokeStyle = "chartreuse";
        ctx.lineWidth = 2 / scale;
        ctx.strokeStyle = "red";
        const fontSize = 11 / scale;
        ctx.font = `${fontSize}px Arial`;
        ctx.fillStyle = "red";
        
        const dataList = msg[i];
        if (dataList==undefined) continue;
        
        ctx.beginPath();
        ctx.moveTo(dataList[0][1][0], dataList[0][1][1]);
        ctx.fillText(dataList[0][0], dataList[0][1][0], dataList[0][1][1] - (5/scale));
        for (let i = 1; i < dataList.length; i++) {
          ctx.lineTo(dataList[i][1][0], dataList[i][1][1]);
          ctx.fillText(dataList[i][0], dataList[i][1][0], dataList[i][1][1] - (5/scale));
        }
        ctx.stroke();
        ctx.closePath()
        
        if (toggleTrackletClick) {
          for (let i = 1; i < dataList.length; i++) {
              const markerSize = 6 / scale;
              const offset = markerSize / 2;
              ctx.beginPath(); 
              ctx.fillStyle = "green";
              ctx.fillRect(dataList[i][1][0] - offset, dataList[i][1][1] - offset, markerSize, markerSize);
              ctx.stroke();
              ctx.closePath();
          }
        }
      }
    }
  });
}

function interpolate(e) {
  if(e)
  e.preventDefault();
  
  var pid = prev_chosen_identity || identities[rectsID[chosen_rect]];
  $.ajax({
    method: "POST",
    url: "interpolate",
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      personID: pid,
      frameID: parseInt(frame_str)-1,
      workerID: workerID,
      datasetName: dset_name
    },
    dataType: "json",
    success: function (msg) {
      alert(msg["message"])
      loader_db("load")
    },
    error: function (msg) {
      console.log("Error while interpolating, running copy from previous/next frame")
      showCopyBtn()
    }
  });
}

function showCopyBtn(){
  var copyBtn = document.getElementById('copyBtn');
  var pid = prev_chosen_identity || identities[rectsID[chosen_rect]];
  copyBtn.innerHTML = "Copy Prev/Next (ID:"+pid+")";
  if (copyBtn.style.display === 'none') {
    copyBtn.style.display = 'inline';
  }
}
function copyPrevOrNext(e) {
  const copyBtn = document.getElementById('copyBtn');
    if (copyBtn) {
        copyBtn.style.display = 'none';
        // rest of the copy logic
    }
  if(e)
  e.preventDefault();
  var pid = prev_chosen_identity || identities[rectsID[chosen_rect]];
  $.ajax({
    method: "POST",
    url: "copy",
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      personID: pid,
      frameID: parseInt(frame_str),
      workerID: workerID,
      datasetName: dset_name
    },
    dataType: "json",
    success: function (msg) {
      loader_db("load")
    },
    error: function (msg) {
      console.log("Error while copying from previous/next frame")
    }
  });
}

function createVideo(e) {
  $.ajax({
    method: "POST",
    url: "createvideo",
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      workerID: workerID,
      datasetName: dset_name
    },
    dataType: "json",
    success: function (msg) {
      alert("Video created.")
    },
    error: function (msg) {
      alert("Error while creating video.")
    }
  });
}

function removeCompleteFlags(e) {
  $.ajax({
    method: "POST",
    url: "resetacflags",
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      workerID: workerID,
      datasetName: dset_name
    },
    dataType: "json",
    success: function (msg) {
      loader_db("load");
      alert("AC flags removed.")
    },
    error: function (msg) {
    }
  });
}

function backSpace() {
  if (rectsID.length > 0) {
    var rid = rectsID[chosen_rect];
    rectsID.splice(chosen_rect, 1);
    var idPers = identities[rid];
    delete validation[idPers];
    delete identities[rid];
    // delete from boxes
    for (var i = 0; i < nb_cams; i++) {
      delete boxes[i][idPers];
    }
    //validation_dict.pop(idPers)
    //identities.pop(idRect)
    //for i in range(NB_PICTURES):
    //  if idPers in person_rect[i]:
    //    person_rect[i].pop(idPers)
    if (chosen_rect == rectsID.length) {
      chosen_rect--;
    }
    // if (zoomOn) {
    //   zoomOut();
    // }
    update();
  }
  return false;
}

function tab() {
  if (rectsID.length <= 1)
    return false;

  chosen_rect++;
  if (zoomOn)
    zoomOut();
  update();
  getTracklet();
  return false;
}

function keyNextFrame() {
  changeFrame('next', parseInt(frame_inc))
}

function keyPrevFrame() {
  changeFrame('prev', parseInt(frame_inc))
}
function space() {
  if (rectsID.length <= 1)
    return false;

  chosen_rect--;
  if (zoomOn)
    zoomOut();
  update();
  return false;
}

function sendAction(action) {
  const box = boxes[0][identities[rectsID[chosen_rect]]];
  const data = {
    "action": action,
    "Xw": box["Xw"],
    "Yw": box["Yw"],
    "Zw": box["Zw"],
    "rotation_theta": box["rotation_theta"],
    "object_size": box["object_size"],
  };
  sendAJAX("action", JSON.stringify(data), rectsID[chosen_rect], rectAction,false);
  update();
  return false;
}

function left() {
  return sendAction({ "move": "left" });
}
function right() {
  return sendAction({ "move": "right" });
}
function up() {
  return sendAction({ "move": "up" });
}
function down() {
  return sendAction({ "move": "down" });
}

function leftLarge() {
  return sendAction({ "move": "left","stepMultiplier":10});
}
function rightLarge() {
  return sendAction({ "move": "right","stepMultiplier":10 });
}
function upLarge() {
  return sendAction({ "move": "up","stepMultiplier":10 });
}
function downLarge() {
  return sendAction({ "move": "down","stepMultiplier":10 });
}

function rotateCW() {
  return sendAction({ "rotate": "cw"});
}
function rotateCCW() {
  return sendAction({ "rotate": "ccw" });
}
function increaseHeight() {
  return sendAction({ "changeSize": { "height": "increase" } });
}
function decreaseHeight() {
  return sendAction({ "changeSize": { "height": "decrease" } });
}
function increaseWidth() {
  return sendAction({ "changeSize": { "width": "increase" } });
}
function decreaseWidth() {
  return sendAction({ "changeSize": { "width": "decrease" } });
}
function increaseLength() {
  return sendAction({ "changeSize": { "length": "increase" } });
}
function decreaseLength() {
  return sendAction({ "changeSize": { "length": "decrease" } });
}

function mergeIDs() {
  const personID1 = document.getElementById("personID1").value;
  const personID2 = document.getElementById("personID2").value;

  $.ajax({
    method: "POST",
    url: 'merge',
    data: {
        csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
        personID1: personID1,
        personID2: personID2,
        workerID: workerID,
        datasetName: dset_name
    },
  success: function (msg) {
    console.log(msg);
    unsavedChanges = false;
    load();
    $("#unsaved").html("All changes saved.");
  }
});
}
// function changeSize(changeWidth, changeHeight, increase) {
//   var ind = getIndx();
//   var pid = identities[rectsID[chosen_rect]];
//   var rect = boxes[ind][pid];
//   var delta = increase ? 1 : -1;

//   if (changeWidth) {
//     rect.x1 -= delta;
//     rect.x2 += delta;

//     if (rect.x2 - rect.x1 < 1) {
//       rect.x1 = rect.x2 - 1;
//     }

//     var widthSize = (rect.x2 - rect.x1) * rect.ratio;
//     updateSize(false, widthSize, ind);
//   }

//   if (changeHeight) {
//     rect.y1 += delta;

//     if (rect.y2 - rect.y1 < 1) {
//       rect.y1 = rect.y2 - 1;
//     }

//     var heightSize = (rect.y2 - rect.y1) * rect.ratio;
//     updateSize(true, heightSize, ind);
//   }

//   boxes[ind][pid] = rect;
//   return false;
// }


// function incrWidth() {
//   var ind = getIndx();
//   var pid = identities[rectsID[chosen_rect]];
//   var rect = boxes[ind][pid];
//   rect.x1 = rect.x1-1;
//   rect.x2 = rect.x2+1;
//   boxes[ind][pid] = rect;

//   var size = (rect.x2-rect.x1)*rect.ratio;
//   updateSize(false,size,ind);
//   return false;

// }

// function decrWidth() {
//   var ind = getIndx();
//   var pid = identities[rectsID[chosen_rect]];
//   var rect = boxes[ind][pid];
//   rect.x1 = rect.x1+1;
//   if(rect.x2 - rect.x1 < 1) {
//     rect.x1 = rect.x2 -1;
//   } else {
//     rect.x2 = rect.x2-1;
//   }
//   boxes[ind][pid] = rect;
//   var size = (rect.x2-rect.x1)*rect.ratio;
//   updateSize(false,size,ind);
//   return false;

// }

// function incrHeight() {

//   var ind = getIndx();
//   var pid = identities[rectsID[chosen_rect]];
//   var rect = boxes[ind][pid];
//   rect.y1 = rect.y1-1;
//   boxes[ind][pid] = rect;

//   var size = (rect.y2-rect.y1)*rect.ratio;
//   updateSize(true,size,ind);
//   return false;

// }

// function decrHeight() {
//   var ind = getIndx();
//   var pid = identities[rectsID[chosen_rect]];
//   var rect = boxes[ind][pid];
//   rect.y1 = rect.y1+1;
//   if(rect.y2 - rect.y1 < 1) {
//     rect.y1 = rect.y2-1;
//   }
//   boxes[ind][pid] = rect;

//   var size = (rect.y2-rect.y1)*rect.ratio;
//   updateSize(true,size,ind);
//   return false;
// }

function getIndx() {
  var h = -1;
  var retInd = -1;
  var pid = identities[rectsID[chosen_rect]];
  for (var i = 0; i < nb_cams; i++) {
    r = boxes[i][pid];
    tpH = Math.abs(r.y1 - r.y2);

    if (tpH > h) {
      h = tpH;
      retInd = i;
    }
  }
  return retInd;
}

function updateSize(height, size, ind) {
  var r = rectsID[chosen_rect];
  var pid = identities[r];
  for (var i = 0; i < nb_cams; i++) {
    rect = boxes[i][pid];
    if (i != ind && rect.y1 != 0) {
      if (height) {
        var b = Math.round(rect.y2 - size / rect.ratio);
        if (rect.y2 - b < 1)
          b = rect.y2 - 1;
        rect.y1 = b;
      } else {
        var delta = size / (2 * rect.ratio);
        var c = Math.round(rect.xMid + delta);
        var a = Math.round(rect.xMid - delta);
        if (c - a < 1)
          a = c - 1;
        rect.x1 = a;
        rect.x2 = c;
      }
    }
    boxes[i][pid] = rect;
  }
  update()
}

function save(e) {
  if (e) e.preventDefault();
  var dims = [];
  
  // Loop through each camera
  for (var camIdx = 0; camIdx < nb_cams; camIdx++) {
    // Skip if this camera's boxes collection is empty
    if (!boxes[camIdx]) continue;
    
    // Process all person IDs in this camera view
    for (var pid in boxes[camIdx]) {
      let box = boxes[camIdx][pid];
      if (!box) continue;
      
      // Add personID explicitly to ensure it's included
      box["personID"] = parseInt(pid);
      dims.push(box);
    }
  }
  
  $.ajax({
    method: "POST",
    url: 'save',
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      data: JSON.stringify(dims),
      ID: frame_str,
      workerID: workerID,
      datasetName: dset_name
    },
    success: function (msg) {
      console.log(msg);
      unsavedChanges = false;
      $("#unsaved").html("All changes saved.");
    }
  });
}

function saveCurrentlySelected() {
  var dims = [];
  var pid = identities[rectsID[chosen_rect]];
  let box = boxes[0][pid];
  if (!box) return;
  box["personID"] = pid;
  dims.push(box);

  $.ajax({
    method: "POST",
    url: 'save',
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      data: JSON.stringify(dims),
      ID: frame_str,
      workerID: workerID,
      datasetName: dset_name
    },
    success: function (msg) {
      console.log(msg);
      unsavedChanges = false;
      $("#unsaved").html("All changes saved.");
    }
  });
}

function load() {
  loader_db('load');
}

function load_prev() {
  loader2('loadprev');

}

function loader(uri) {

  $.ajax({
    method: "POST",
    url: uri,
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      ID: frame_str,
      workerID: workerID,
      datasetName: dset_name
    },
    dataType: 'json',
    success: function (msg) {
      boxesLoaded=false;
      clean();
      var maxID = 0;
      for (var i = 0; i < msg.length; i++) {
        var rid = msg[i][0].rectangleID;
        var indof = rectsID.indexOf(rid);
        if (indof == -1) {
          rectsID.push(rid);
          saveRectLoad(msg[i]);
          chosen_rect = rectsID.length - 1;
          identities[rid] = msg[i][nb_cams];
          var pid = msg[i][nb_cams];
          if (pid > maxID)
            maxID = pid;
          if (uri == "loadprev")
            validation[pid] = false;
          else
            validation[pid] = msg[i][parseInt(nb_cams) + 1];
        }
      }
      personID = maxID + 1;
      update();
      $("#unsaved").html("All changes saved.");
      unsavedChanges = false;
      boxesLoaded=true;
    },
    error: function (msg) {
      if (uri == "load")
        load_prev();
    }
  });
}

function loader2(uri) {

  $.ajax({
    method: "POST",
    url: uri,
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      ID: frame_str,
      workerID: workerID,
      datasetName: dset_name
    },
    dataType: 'json',
    success: function (msg) {
      clean();
      var maxID = 0;
      for (var i = 0; i < msg.length; i++) {
        const box = msg[i];
        var rid = box.rectangleID;
        var indof = rectsID.indexOf(rid);
        if (indof == -1) {
          rectsID.push(rid);
          var pid = box.personID;
          identities[rid] = pid;
          sendAJAX("action", JSON.stringify(box), rid, rectAction,true);
          if (pid > maxID)
            maxID = pid;
          if (uri == "loadprev")
            validation[pid] = false;
          else
            validation[pid] = true;
        }
      }
      personID = maxID + 1;
      update();
      $("#unsaved").html("All changes saved.");
    },
    error: function (msg) {
      if (uri == "load")
        load_prev();
    }
  });
}function loader_db(uri) {
  $.ajax({
      method: "POST",
      url: uri,
      data: {
          csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
          ID: frame_str,
          workerID: workerID,
          datasetName: dset_name
      },
      dataType: 'json',
      success: function(annotations) {
        console.log("Loading annotations")
          boxesLoaded = false;
          clean();
          let maxID = 0;

          // Initialize boxes array for each camera
          for (let i = 0; i < nb_cams; i++) {
              boxes[i] = {};
          }

          annotations.forEach(ann => {
              // console.log(ann.cuboid)
              const rid = ann.rectangleID;
              const pid = ann.person_id;
              
              maxID = Math.max(maxID, pid);
              
              if (!rectsID.includes(rid)) {
                  rectsID.push(rid);
                  chosen_rect = rectsID.length - 1;
              } else {
                  chosen_rect = rectsID.indexOf(rid);
              }
              
              identities[rid] = pid;
              
              // if (ann.cuboid) { console.log(ann); }
              
              boxes[ann.cameraID][pid] = ann;
              validation[pid] = (uri !== "loadprev");
          });

          if (prev_chosen_identity!=undefined){
            if (prev_chosen_identity in boxes[0]){
              chosen_rect =  rectsID.indexOf(boxes[0][prev_chosen_identity].rectangleID)
              getTracklet();
              displayCrops(frame_str, prev_chosen_identity, timeview_canv_idx); //display crops --timeview.js
              showCopyBtn()
            }
            else {
              // interpolate()
            }
          }
          
          personID = maxID + 1;
          boxesLoaded=true;
          $("#unsaved").html("All changes saved.");
          
          if (zoomOn) {
            zoomOut();
            zoomIn();
          }

          update();
        },
        error: function (msg) {
          if (uri == "load")
            load_prev();
        }
  });
}

// function loader_db(uri) {
//   // console.log('loading from db');
//   $.ajax({
//     method: "POST",
//     url: uri,
//     data: {
//       csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
//       ID: frame_str,
//       workerID: workerID,
//       datasetName: dset_name
//     },
//     dataType: 'json',
//     success: function (msg) {
//       console.log(msg[0]);
//       boxesLoaded=false;
//       clean();
//       var maxID = 0;
//       for (var i = 0; i < msg[0].length; i++) {
//         var rid = msg[0][i].rectangleID;
//         var indof = rectsID.indexOf(rid);
        
//         if (indof == -1) {
//           rectsID.push(rid);
//           chosen_rect = rectsID.length - 1;
//         }else{
//           chosen_rect = rectsID[indof];
//           var pid = msg[0][i].person_id
//           identities[rid] = pid;
//         }
        
//         var pid = msg[0][i].person_id
//         identities[rid] = pid;
        
//         for (var cami = 0; cami < nb_cams; cami++) {
//           boxes[cami][pid] = msg[cami][i];
//           // console.log('chosen rect id: ', chosen_rect, 'person id: ', pid, 'with boxes: ', boxes[cami][pid]);
//           }
//         if (pid > maxID)
//           maxID = pid;
//         if (uri == "loadprev")
//           validation[pid] = false;
//         else
//           validation[pid] = true;
          
//       }

//       if (prev_chosen_identity!=undefined){
//         if (prev_chosen_identity in boxes[0]){
//           chosen_rect =  rectsID.indexOf(boxes[0][prev_chosen_identity].rectangleID)
//           getTracklet();
//           displayCrops(frame_str, prev_chosen_identity, timeview_canv_idx); //display crops --timeview.js
//           showCopyBtn()
//         }
//         else {
//           interpolate()
//         }
//       }
      
//       personID = maxID + 1;
//       boxesLoaded=true;
//       $("#unsaved").html("All changes saved.");
//       update();
//     },
//     error: function (msg) {
//       if (uri == "load")
//         load_prev();
//     }
//   });
// }

function clean() {
  for (var i = 0; i < nb_cams; i++) {
    boxes[i] = {};
    rectsID = [];
    validation = {};
    identities = {};
    personID = 0;
    chosen_rect = 0;
  }
  update();
}

// Add these variables at the top with other global variables
const PRELOAD_FRAMES = 3; // Number of frames to preload in each direction
const preloadedImages = new Map(); // Cache for preloaded images
const prefload_increment = 10;


// Add these variables at the top
let localDirectoryHandle = "/Users/engilber/work/dataset/local_copy_seq_2";
let useLocalFiles = true;

// Add this new function to handle preloading
function preloadFrames(currentFrame, frameStrings) {
    const framesToPreload = [];
    // Get frame numbers before current frame
    // for (let i = 1; i <= PRELOAD_FRAMES; i++) {
    //     framesToPreload.push(parseInt(currentFrame) - i * prefload_increment);
    // }
    // Get frame numbers after current frame
    for (let i = 1; i <= PRELOAD_FRAMES; i++) {
        framesToPreload.push(parseInt(currentFrame) + i * prefload_increment);
    }

    // Preload frames
    framesToPreload.forEach(frameNum => {
        // Skip if already preloaded
        if (preloadedImages.has(frameNum)) return;

        // Request frame strings for this frame
        $.ajax({
            method: "POST",
            url: 'changeframe',
            data: {
                csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
                order: frameNum > currentFrame ? 'next' : 'prev',
                frameID: currentFrame,
                incr: Math.abs(frameNum - currentFrame),
                workerID: workerID,
                datasetName: dset_name
            },
            dataType: "json",
            success: function(msg) {
                const frameImages = new Map();
                
                // Preload images for each active camera
                activeCameras.forEach((camName) => {
                    const img = new Image();
                    const index = cameraPaths.indexOf(camName);
                    let path;
                    if (useLocalFiles) {
                        path = `file://${localDirectoryHandle}/${camName}/${msg.frame_strs[camName]}`;
                    } else {
                        path = '/static/gtm_hit/dset/' + dset_name + '/' +
                               (useUndistorted == "True" ? "undistorted_" : "") +
                               'frames/' + camName + '/' + msg.frame_strs[camName];
                    }
                    img.src = path;
                    frameImages.set(camName, img);
                });

                preloadedImages.set(frameNum, {
                    frameStrings: msg.frame_strs,
                    images: frameImages
                });
            }
        });
    });
}


// Modify the changeFrame function to use preloaded images
function changeFrame(order, increment) {
  // if(boxesLoaded) saveCurrentlySelected();
  if (nblabeled >= to_label) {
      return true;
  }
  boxesLoaded=false;
  $.ajax({
      method: "POST",
      url: 'changeframe',
      data: {
          csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
          order: order,
          frameID: frame_str,
          incr: increment,
          workerID: workerID,
          datasetName: dset_name
      },
      dataType: "json",
      success: function (msg) {
          frame_str = msg['frame'];
          nblabeled = msg['nblabeled'];
          frameStrs = msg['frame_strs']
          if (nblabeled >= to_label) {
              var button = document.getElementById("changeF");
              button.href = "/gtm_hit/" + dset_name + "/"+ workerID + "/processFrame";
              button.text = "Finish";
          }
          loadcount = 0;
          $("#loader").show();
          fstr = parseInt(frame_str);
          $("#frameID").html("Frame ID: " + fstr.toString() + "&nbsp;&nbsp;");
          
          if (useUndistorted=="True") undistort_frames_path="undistorted_"
          activeCameras.forEach((camName) =>{
            const index = cameraPaths.indexOf(camName);
            imgArray[index].src = frameStrs[camName];//'/static/gtm_hit/dset/'+dset_name+'/'+undistort_frames_path+'frames/' + camName + '/' + frameStrs[camName];
          })
          // for (var i = 0; i < nb_cams; i++) {
          //     imgArray[i].src = '/static/gtm_hit/dset/'+dset_name+'/'+undistort_frames_path+'frames/' + camName[i] + '/' + frameStrs[camName[i]];
          //     console.log(imgArray[i].src)
          // }
      },
      complete: function (msg) {
          prev_chosen_identity= identities[rectsID[chosen_rect]];
          clean()
          load();
          showCopyBtn()
      }
  });
}


function next() {
  changeFrame('next', 1);
}

function prev() {
  changeFrame('prev', 1);
}

function nextI() {
  changeFrame('next', 10);
}

function prevI() {
  changeFrame('prev', 10);
}

function validate() {
  var rid = rectsID[chosen_rect];
  var idPers = identities[rid];
  validation[idPers] = true;
  return false;
}

function changeID(opt) {
  const propagateElement = document.getElementById('propagate');
  const conflictsElement = document.getElementById('conflicts');
  const splitFrameElement = document.getElementById('splitFrame');
  const propagateValue = propagateElement.value;
  const conflictsValue = conflictsElement.value;
  const splitFrameValue = splitFrameElement.value;

  var newID = parseInt($("#pID").val());
  if (opt==undefined)opt="";
  const old_chosen_rect = chosen_rect;
  $.ajax({
    method: "POST",
    url: "changeid",
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      newPersonID: newID,
      frameID: parseInt(frame_str),
      personID: identities[rectsID[chosen_rect]],
      splitFrame: parseInt(splitFrameValue),
      workerID: workerID,
      datasetName: dset_name,
      options: JSON.stringify({'propagate':propagateValue,'conflicts':conflictsValue})
    },
    dataType: "json",
    success: function (msg) {
      loader_db('load');
      $("#pID").val(newID);
      chosen_rect = old_chosen_rect;
    }
  });
}

function personAction(opt) {
  if (opt==undefined)return false;
  const old_chosen_rect = chosen_rect;
  prev_chosen_identity = identities[rectsID[chosen_rect]];
  $.ajax({
    method: "POST",
    url: "person",
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      personID: identities[rectsID[chosen_rect]],
      workerID: workerID,
      datasetName: dset_name,
      options: JSON.stringify(opt)
    },
    dataType: "json",
    success: function (msg) {
      loader_db('load');
      if (!opt["delete"] )chosen_rect = old_chosen_rect;
      
    }
  });
}


function sendAJAX(uri, data, id, suc, load) {
  $.ajax({
    method: "POST",
    url: uri,
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      data: data,
      ID: id,
      workerID: workerID,
      datasetName: dset_name
    },
    dataType: "json",
    success: function (msg) {
      if (msg.length > 0)
        suc(msg, id, load);
      update();
    }
  });
}

function saveRect(msg, pid) {
  for (var i = 0; i < msg.length; i++) {
    var ind = msg[i].cameraID;
    boxes[ind][pid] = msg[i];
  }
}

function saveRectLoad(msg) {
  for (var i = 0; i < msg.length - 2; i++) {
    var ind = msg[i].cameraID;
    boxes[ind][msg[nb_cams]] = msg[i];
  }
}

function rectAction(msg, id, load) {
  var pid = identities[id];
  // if(typeof boxes[0][pid] == "undefined") {
  //   return false;
  // }
  if (typeof pid == "undefined") {
    return false;
  }
  var index = rectsID.indexOf(id);
  var nextRect = msg[0].rectangleID;
  rectsID.splice(index, 1);
  rectsID.push(nextRect);
  chosen_rect = rectsID.length - 1;
  if (load && prev_chosen_identity!=undefined){
    if (prev_chosen_identity in boxes[0])
      chosen_rect =  rectsID.indexOf(boxes[0][prev_chosen_identity].rectangleID)
  }
  identities[nextRect] = pid;
  if (nextRect != id) delete identities[id];
  validation[pid] = true;

  for (var i = 0; i < msg.length; i++) {
    var f = msg[i];
    var ind = f.cameraID;
    var oldRect = boxes[ind][pid];

    var newRect = msg[i];
    // var heightR = Math.abs(oldRect.y1-oldRect.y2)*oldRect.ratio;
    // var widthR = Math.abs(oldRect.x1-oldRect.x2)*oldRect.ratio;

    // if(newRect.ratio > 0){
    //   newRect.y1 = Math.round(newRect.y2 - (heightR/newRect.ratio));
    //   var delta = widthR/(2*newRect.ratio);
    //   newRect.x2 = Math.round(newRect.xMid + delta);
    //   newRect.x1 = Math.round(newRect.xMid - delta);
    // }
    boxes[ind][pid] = newRect;
  }
}

function update() {
  tracklet = null;
  if (chosen_rect==undefined) chosen_rect = 0;
  chosen_rect = ((chosen_rect % rectsID.length) + rectsID.length) % rectsID.length;
  $("#pID").val(identities[rectsID[chosen_rect]]);

  drawRect();
  // if (toggle_ground)
  //   drawGround();

  var d = document.getElementById("changeF");
  if (d != null) {
    if (rectsID.length > 1) {
      if (checkRects())
        d.className = d.className.replace(" disabled", "");
      else if (d.className.indexOf("disabled") == -1)
        d.className = d.className + " disabled";
    } else if (d.className.indexOf("disabled") == -1) {
      d.className = d.className;// + " disabled";
    }
  }
  unsavedChanges = true;
  $("#unsaved").html("Unsaved changes.");
}


function drawDot(event) {
  const { offsetX, offsetY } = event;
  var x = offsetX * frame_size[0] / this.clientWidth;
  var y = offsetY * frame_size[1] / this.clientHeight;
  const dotRadius = 5;
  var c = event.currentTarget
  var ctx = c.getContext("2d");
  ctx.beginPath();
  ctx.arc(x, y, 2, 0, 2 * Math.PI);
  ctx.fillStyle = "black";
  ctx.fill();
  ctx.closePath();

}

function drawLine(ctx, v1, v2) {
  if (!v1?.[0] || !v1?.[1] || !v2?.[0] || !v2?.[1]) return;
  
  // Get current transform scale to adjust line width
  const scale = ctx.getTransform().a;
  
  ctx.beginPath();
  ctx.strokeStyle = "pink";
  ctx.lineWidth = 2 / scale; // Adjust line width based on zoom
  ctx.moveTo(v1[0], v1[1]);
  ctx.lineTo(v2[0], v2[1]);
  ctx.stroke();
  ctx.closePath();
}

function drawCuboid(ctx, vertices) {
  // Draw lines for the base rectangle
  drawLine(ctx, vertices[0], vertices[1]);
  drawLine(ctx, vertices[1], vertices[3]);
  drawLine(ctx, vertices[2], vertices[3]); 
  drawLine(ctx, vertices[2], vertices[0]);

  // Draw lines for the top rectangle
  drawLine(ctx, vertices[4], vertices[5]);
  drawLine(ctx, vertices[5], vertices[7]);
  drawLine(ctx, vertices[6], vertices[7]);
  drawLine(ctx, vertices[6], vertices[4]);

  // Draw lines connecting the base and top rectangles
  drawLine(ctx, vertices[0], vertices[4]);
  drawLine(ctx, vertices[1], vertices[5]);
  drawLine(ctx, vertices[2], vertices[6]);
  drawLine(ctx, vertices[3], vertices[7]);

  //draw direction
  if (vertices.length>8){
    drawLine(ctx, vertices[8], vertices[9]);

    // mark the base point with scale-adjusted size
    const scale = ctx.getTransform().a;
    const size = 5 / scale;
    
    ctx.beginPath();
    ctx.fillStyle = "red";
    ctx.fillRect(vertices[8][0] - size, vertices[8][1] - size, size * 2, size * 2);
    ctx.stroke();
    ctx.closePath();
  }
}

function removePersonFromAll() {
  const isConfirmed = confirm("Are you sure you want to delete this object from all frames? This cannot be undone.");
  if (isConfirmed) {
    personAction({'delete':true});
  }
}


function drawRect() {

  cameraPaths.forEach((camName, index) => {
    var c = document.getElementById("canv" + camName);
    if (!c) {
        console.error("Canvas with ID canv" + camName + " not found.");
        return;
    }
    var ctx = c.getContext('2d');
    ctx.clearRect(0, 0, c.width, c.height);
    
    // Skip this iteration if image isn't loaded by returning early
    if (!imgArray[index].complete || imgArray[index].naturalWidth === 0) {
        return;
    }
    
    ctx.drawImage(imgArray[index], 0, 0);
  });

  var heightR = 0;
  var widthR = 0;
  var sumH = 0;
  // console.log(boxes)
  for (key in boxes) {
    if (boxes[key] == undefined) continue;
    for (var r = 0; r < rectsID.length; r++) {
      var field = boxes[key][identities[rectsID[r]]];
      if (field == undefined) continue;

      if (field.y1 != -1 && field.y2 != -1 && field.x1 != -1) {
        var c = document.getElementById("canv" + (cameraPaths[field.cameraID]));
        var ctx = c.getContext("2d");
        const scale = ctx.getTransform().a;
        
        //show only selected 
        if (!(r == chosen_rect) && !toggle_unselected) continue;
        //draw cuboid
        if (toggle_cuboid && field.cuboid && field.cuboid.length!=0) drawCuboid(ctx, field.cuboid);

        var w = field.x2 - field.x1;
        var h = field.y2 - field.y1;
        if (selectedBoxes.some(selected => rectsID[r] === selected.rectID)) {
          ctx.strokeStyle = "magenta";  // Distinct color for merge-selected boxes
          ctx.lineWidth = 5 / scale;
        }
        else if (r == chosen_rect) {
          ctx.strokeStyle = "cyan";
          ctx.lineWidth = 4 / scale;
          heightR += (field.y2 - field.y1) * field.ratio;
          widthR += (field.x2 - field.x1) * field.ratio;
          sumH += 1;
        
        } else {
          var pid = identities[field.rectangleID];
          if (validation[pid])
            ctx.strokeStyle = "white";
          else
            ctx.strokeStyle = "yellow";

          if (field.annotation_complete) ctx.strokeStyle = "green";
          ctx.lineWidth = 4 / scale;
        }
        
        ctx.beginPath();
        ctx.rect(field.x1, field.y1, w, h);
        ctx.stroke();
        ctx.closePath();

        // Scale the center point marker size
        const markerSize = 10 / scale;
        ctx.beginPath();
        ctx.fillStyle = "green";
        ctx.fillRect(field.xMid - markerSize/2, field.y1 - markerSize/2, markerSize, markerSize);
        ctx.stroke();
        ctx.closePath();

        // Scale the ID background rectangle
        const idBoxHeight = 20 / scale;
        const idBoxWidth = 50 / scale;
        ctx.beginPath();
        ctx.fillStyle = "black";
        if (field.annotation_complete) ctx.fillStyle = "green";
        ctx.fillRect(field.x1, field.y1 - (27/scale), idBoxWidth, idBoxHeight);
        ctx.stroke();
        ctx.closePath();

        if (r == chosen_rect) {
          ctx.fillStyle = "cyan";
        } else {
          ctx.fillStyle = "white";
        }
        
        // Scale the font size
        const fontSize = 20 / scale;
        ctx.font = `${fontSize}px Arial`;
        ctx.fillText("ID:" + identities[field.rectangleID], field.x1, field.y1 - (10/scale));
      }
    }
  }
  if (chosen_rect >= 0) {
    let pid = identities[rectsID[chosen_rect]];
    let box = boxes[key][pid];
    if (box) {
      //round to 2 decimal places
      $("#pHeight").text("Height: "+box.object_size[0].toFixed(3)); 
      $("#pWidth").text("Width: "+box.object_size[1].toFixed(3));
      $("#pLength").text("Length: "+box.object_size[2].toFixed(3));
      $("#pID").text(pid);
    }
    else {
      $("#pHeight").text(-1);
      $("#pWidth").text(-1);
      $("#pLength").text(-1);
      $("#pID").text(-1);
    }

  } else {
    $("#pHeight").text(-1);
    $("#pWidth").text(-1);
    $("#pLength").text(-1);
    $("#pID").text(-1);
  }

}

// function drawGround() {
//   for (var i = 0; i < nb_cams; i++) {
//     var c = document.getElementById("canv" + (i + 1));
//     var ctx = c.getContext("2d");
//     ctx.strokeStyle = "chartreuse";
//     ctx.lineWidth = "2";
//     ctx.beginPath();

//     ctx.moveTo(bounds[i][0], bounds[i][1]);
//     for (var j = 2; j < bounds[i].length; j = j + 2) {
//       if (bounds[i][j] >= 0) {
//         ctx.lineTo(bounds[i][j], bounds[i][j + 1]);
//       }
//     }
//     ctx.stroke();
//     ctx.closePath();

//   }
// }

// function drawArrows(ctx, idx) {
//   ctx.drawImage(arrArray[idx], 0, 0);
// }

function zoomControl() {
  if (rectsID.length > 0) {
    if (!zoomOn) {
      zoomIn();
    } else {
      zoomOut();
    }

  }
  update();
}

function isBoundingBoxInCanvas(box, canvas) {
  const canvasWidth = canvas.width;
  const canvasHeight = canvas.height;

  const boxLeft = Math.min(box.x1, box.x2);
  const boxRight = Math.max(box.x1, box.x2);
  const boxTop = Math.min(box.y1, box.y2);
  const boxBottom = Math.max(box.y1, box.y2);

  const isBoxLeftInCanvas = boxLeft >= 0 && boxLeft < canvasWidth;
  const isBoxRightInCanvas = boxRight > 0 && boxRight <= canvasWidth;
  const isBoxTopInCanvas = boxTop >= 0 && boxTop < canvasHeight;
  const isBoxBottomInCanvas = boxBottom > 0 && boxBottom <= canvasHeight;

  return (isBoxLeftInCanvas || isBoxRightInCanvas) &&
    (isBoxTopInCanvas || isBoxBottomInCanvas);
}




function zoomIn() {
  for (var i = 0; i < nb_cams; i++) {
    var pid = identities[rectsID[chosen_rect]];
    var r = boxes[i][pid];

    var c = document.getElementById("canv" + cameraPaths[i]);
    if (!isBoundingBoxInCanvas(r, c)) {
      zoomState[i].scale = 1; // Reset zoom for canvases without bounding boxes
      continue;
    }

    // Calculate zoom ratio
    var zoomRatio = c.height * 60 / (100 * (r.y2 - r.y1));
    if (zoomRatio === Infinity || zoomRatio === null) continue;

    // Update zoom state
    zoomState[i].scale *= zoomRatio;

    // Calculate translation
    var originX = r.xMid - c.width / (2 * zoomRatio);
    var originY = r.y1 - 12.5 * c.height / (100 * zoomRatio);
    zoomState[i].translateX += -originX; //* zoomRatio;
    zoomState[i].translateY += -originY;// * zoomRatio;

    console.log(i, zoomState[i].scale, zoomState[i].translateX, zoomState[i].translateY);

    // Apply transformations
    var ctx = c.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0); // Reset canvas transformations
    ctx.scale(zoomState[i].scale, zoomState[i].scale);
    ctx.translate(zoomState[i].translateX, zoomState[i].translateY);
  }
  zoomOn = true;
  return false;
}

function zoomOut() {
  for (var i = 0; i < nb_cams; i++) {
    var c = document.getElementById("canv" + cameraPaths[i]);

    // Reset transformations using the inverse of the current zoom state
    var ctx = c.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0); // Reset canvas transformations
    zoomState[i].scale = 1; // Reset scale
    zoomState[i].translateX = 0; // Reset translation
    zoomState[i].translateY = 0;
  }
  zoomOn = false;
  return false;
}

// function zoomIn() {
//   for (var i = 0; i < nb_cams; i++) {
//     var pid = identities[rectsID[chosen_rect]];
//     var r = boxes[i][pid];

//     var c = document.getElementById("canv" + cameraPaths[i]);
//     if (isBoundingBoxInCanvas(r, c)) { zoomratio[i] = c.height * 60 / (100 * (r.y2 - r.y1)); }
//     else {
//       zoomratio[i] = null;
//       continue;
//     }
//     if (zoomratio[i] != Infinity) {

//       var ctx = c.getContext('2d');
//       c.width = c.width / zoomratio[i];
//       c.height = c.height / zoomratio[i];
//       var originx = r.xMid - c.width / 2;
//       // var originx = r.xMid;
//       var originy = r.y1 - 12.5 * c.height/100;//c.clientHeight / 100;
//       // ctx.scale(1.75,1.75);z
//       ctx.translate(-originx, -originy);

//     }
//   }
//   zoomOn = true;
//   return false;

// }

// function zoomOut() {
//   for (var i = 0; i < nb_cams; i++) {
//     var c = document.getElementById("canv" + cameraPaths[i]);
//     if (zoomratio[i] != undefined && zoomratio[i] != Infinity) {
//       c.width = c.width * zoomratio[i];
//       c.height = c.height * zoomratio[i];
//     }
//   }
//   zoomOn = false;
//   return false;
// }


function toggleGround() {
  if (toggle_ground == false)
    toggle_ground = true;
  else
    toggle_ground = false;
  update();
  return false;
}

function toggleCuboid() {
  if (toggle_cuboid == false)
    toggle_cuboid = true;
  else
    toggle_cuboid = false;
  update();
  return false;
}
function toggleUnselected() {
  if (toggle_unselected == false)
    toggle_unselected = true;
  else
    toggle_unselected = false;
  update();
  return false;
}

function toggleOrientation() {
  if (toggle_orientation == false)
    toggle_orientation = true;
  else
    toggle_orientation = false;
  update();
  return false;
}

function checkRects() {
  return true
  var c = 0;
  for (var i = 0; i < rectsID.length; i++) {
    var personID = identities[rectsID[i]];
    if (validation[personID])
      c++;
  }
  if (c > 1)
    return true;
  else
    return false;
}


function load_file(f) {
  var re = f.match(/_(.*)\./);
  if (re == null)
    var frame_string = f.split(".")[0];
  else
    var frame_string = f.match(/_(.*)\./).pop();
  $.ajax({
    method: "POST",
    url: "loadfile",
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      ID: f
    },
    dataType: 'json',
    success: function (msg) {
      clean();
      load_frame(frame_string);
      var maxID = 0;
      for (var i = 0; i < msg.length; i++) {
        var rid = msg[i][0].rectangleID;
        var indof = rectsID.indexOf(rid);
        if (indof == -1) {
          rectsID.push(rid);
          saveRectLoad(msg[i]);
          chosen_rect = rectsID.length - 1;
          identities[rid] = msg[i][7];
          var pid = msg[i][7];
          if (pid > maxID)
            maxID = pid;

          validation[pid] = msg[i][8];
        }
        personID = maxID + 1;
        update();
      }
    }
  });

}

async function load_frame(frame_string) {
  loadcount = 0;
  $("#loader").show();
  frame_str = frame_string.replace(/^0*/, "");
  $("#frameID").html("Frame ID: " + frame_str + "&nbsp;&nbsp;");
  
  if (useUndistorted=="True") undistort_frames_path="undistorted_"
  var frameStrs = JSON.parse('{{ frame_strs|safe }}');
  
  for (var i = 0; i < nb_cams; i++) {
      var imgSrc = frameStrs[camName[i]];//'/static/gtm_hit/dset/'+dset_name+'/'+undistort_frames_path+'frames/' + camName[i] + '/' + frameStrs[camName[i]];
      const loadedImg = await loadImage(imgSrc);
      if (loadedImg !== null) {
          imgArray[i].src = imgSrc;
      }
  }
  clean();
  update();
}

// function fetchFrameStrings(frame_str) {
//   $.ajax({
//       method: "POST",
//       url: 'frame',
//       data: {
//           csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
//           ID: frame_str,
//           workerID: workerID,
//           datasetName: dset_name
//       },
//       dataType: "json",
//       success: function (msg) {
//           frameStrs = msg['frame_strs'];
//           // Now load the images with the received frame strings
//           for (var i = 0; i < nb_cams; i++) {
//               if (useUndistorted=="True") undistort_frames_path="undistorted_"
//               imgArray[i].src = '/static/gtm_hit/dset/'+dset_name+'/'+undistort_frames_path+'frames/' + camName[i] + '/' + frameStrs[camName[i]];
//           }
//       }
//   });
// }


function autoAlignCurrent() {
  if (chosen_rect === -1 || chosen_rect >= rectsID.length) {
    console.error("No rectangle selected");
    return false;
  }
  
  const rectID = rectsID[chosen_rect];
  const pid = identities[rectID];
  
  if (typeof pid === "undefined") {
    console.error("No person ID associated with the selected rectangle");
    return false;
  }
  
  const box = boxes[0][pid];
  const data = {
    "personID": pid,
    "rectangleID": rectID,
    "frameID": frame_str,
    "Xw": box["Xw"],
    "Yw": box["Yw"],
    "Zw": box["Zw"],
    "rotation_theta": box["rotation_theta"],
    "object_size": box["object_size"]
  };
  
  sendAJAX("autoaligncurrent", JSON.stringify(data), rectID, rectAction, false);
  update();
  return false;
}


