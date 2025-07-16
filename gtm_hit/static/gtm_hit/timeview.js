var timeview_canv_idx;

async function displayCrops(frame, pid,camid, numPrevFrames = 5, numFutureFrames = 5) {
    document.getElementById("crops-container").style.display = "flex";
    const cropsContainer = $("#crops-container");
    cropsContainer.empty();
    //cropsContainer.style.display = "flex";
    const currentFrame = parseInt(frame);
    document.getElementById("crops-container").innerHTML = '<button id="close-button" style="position: absolute; top: 0; left: 0;" onclick="hideCrops()">X</button>';
    $.ajax({
        method: "POST",
        url: "timeview",
        data: {
          csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
          personID: pid,
          frameID: parseInt(frame_str),
          viewID: camid,
          workerID: workerID,
          datasetName: dset_name
        },
        dataType: "json",
        success: function (msg) {
        async function displaycrop(msg) {
          // for (let i = 0; i < msg.length; i++) {
          for (let i = 0; i < msg.length; i++) {
            var box = msg[i];
            const cropFrame =box.frameID;
            if (cropFrame < 0) {
              continue;
            }
            // const frameUrl = getFrameUrl(cropFrame, camid);
            // console.log("Frame url:" + frameUrl);
            // const cropImg = await loadImage(frameUrl);
            const frameUrl = await getFrameUrl(cropFrame, camid);
            console.log("Frame url:" + frameUrl);
            const cropImg = await loadImage(frameUrl);

            
            if (cropImg !== null) {
              const canvas = createCroppedCanvas(cropImg, box, cropFrame, currentFrame);
              canvas.className = "crop-image";
              canvas.id = cropFrame;
              canvas.onclick = function() {
                if (cropFrame < frame_str) changeFrame("prev",frame_str-cropFrame);
                else
                changeFrame("next",cropFrame-frame_str);
              };
              // Set fixed height while maintaining aspect ratio
              canvas.style.height = "150px"; // Adjust this value as needed
              canvas.style.width = "auto";
              cropsContainer.append(canvas);
            }
          }
        }
        displaycrop(msg);
    }

      });

  }
// async function displayCrops(frame, pid, numPrevFrames = 5, numFutureFrames = 5) {
//     document.getElementById("crops-container").style.display = "flex";
//     const cropsContainer = $("#crops-container");
//     cropsContainer.empty();
    
//     const currentFrame = parseInt(frame);
//     document.getElementById("crops-container").innerHTML = '<button id="close-button" style="position: absolute; top: 0; left: 0;" onclick="hideCrops()">X</button>';

//     // Create a container for each camera view
//     activeCameras.forEach(camid => {
//         const cameraContainer = $('<div>').addClass('camera-crop-container');
//         cameraContainer.append(`<h4>Camera ${camid}</h4>`);
//         cropsContainer.append(cameraContainer);

//         $.ajax({
//             method: "POST",
//             url: "timeview",
//             data: {
//                 csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
//                 personID: pid,
//                 frameID: parseInt(frame_str),
//                 viewID: camid,
//                 workerID: workerID,
//                 datasetName: dset_name
//             },
//             dataType: "json",
//             success: async function(msg) {
//                 for (let i = 0; i < msg.length; i++) {
//                     const box = msg[i];
//                     const cropFrame = box.frameID;
                    
//                     if (cropFrame < 0) continue;

//                     const frameUrl = await getFrameUrl(cropFrame, camid);
//                     const cropImg = await loadImage(frameUrl);

//                     if (cropImg !== null) {
//                         const canvas = createCroppedCanvas(cropImg, box, cropFrame, currentFrame);
//                         canvas.className = "crop-image";
//                         canvas.id = `${camid}-${cropFrame}`;
//                         canvas.onclick = function() {
//                             if (cropFrame < frame_str) changeFrame("prev", frame_str-cropFrame);
//                             else changeFrame("next", cropFrame-frame_str);
//                         };
//                         canvas.style.height = "150px";
//                         canvas.style.width = "auto";
                        
//                         // Add frame number label
//                         const cropWrapper = $('<div>').addClass('crop-wrapper');
//                         cropWrapper.append(canvas);
//                         cropWrapper.append(`<div class="frame-label">Frame ${cropFrame}</div>`);
                        
//                         cameraContainer.append(cropWrapper);
//                     }
//                 }
//             }
//         });
//     });
// }


  
  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = src;
    });
  }
  
  function createCroppedCanvas(image, box, cropFrame, currentFrame) {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    const cropWidth = box.x2 - box.x1;
    const cropHeight = box.y2 - box.y1;
    const ratio = 2;
    canvas.width = cropWidth*ratio;
    canvas.height = cropHeight*ratio;
  
    ctx.drawImage(
      image,
      box.x1,
      box.y1,
      cropWidth,
      cropHeight,
      0,
      0,
      cropWidth*ratio,
      cropHeight*ratio
    );
    
    // Calculate font size based on final display height of 150px
    const displayScale = cropHeight / 150;
    const fontSize = Math.round(48 * displayScale);
    
    // Add frame number text
    ctx.font = `${fontSize}px Arial`;
    ctx.fillStyle = "red";
    ctx.fillText(`${cropFrame}`, 5, fontSize + 4);

    // Highlight the current frame with a red border
    if (cropFrame === currentFrame) {
        ctx.strokeStyle = "red";
        ctx.lineWidth = 5;
        ctx.strokeRect(0, 0, cropWidth*ratio, cropHeight*ratio);
    }

    return canvas;
  }
  
// function getFrameUrl(frame, cameraID) {
//     const frameStr = String(frame).padStart(8, "0");
//     const camName = String(cameraID);
//     // const url = `/static/gtm_hit/dset/${dset_name}/${undistort_frames_path}frames/${camName}/${frameStr}.jpg`;
//     const url = `/static/gtm_hit/dset/${dset_name}/${undistort_frames_path}frames/${camName}/${frameStr}.jpg`;

//     return url;
//   }
  
// function getFrameUrl(frame_str, cameraID) {
//   $.ajax({
//     method: "POST",
//     url: 'serve_frame',
//     data: {
//         csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
//         camera_name: cameraID,
//         frame_number: frame_str,
//     },
//     dataType: "json",
//     success: function (msg) {
//         const frame_str = msg['frame_string'];
//         return frame_str;
    
//     }})}
    function getFrameUrl(frame_str, cameraID) {
      return new Promise((resolve, reject) => {
          $.ajax({
              method: "POST",
              url: 'serve_frame', 
              data: {
                  csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
                  camera_name: cameraID,
                  frame_number: frame_str,
              },
              dataType: "json",
              success: function (msg) {
                      resolve(msg['frame_string']);
              },
              error: function(xhr, status, error) {
                  reject(error);
              }
          });
      });
  }
  