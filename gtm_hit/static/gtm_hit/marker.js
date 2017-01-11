var rectsID = [];
var boxes = {};
var chosen_rect;
var imgArray = [];
var arrArray = [];
var validation = {};
var identities = {};
var personID = 0;
var cameras = 7;
var camName = '';
var loadcount = 0;
var zoomOn = false;
var zoomratio = [];
var rotation = [50,230,150,75,265,340,80];
var bounds = [[0,396,1193,180,1883,228,1750,1080],[0,344,1467,77,1920,82,-1,-1],
              [97,1080,73,273,864,202,1920,362],[0,444,1920,261,-1,-1,-1,-1],
              [0,435,1920,403,-1,-1,-1,-1],[0,243,29,203,656,191,1920,442],
              [0,244,1920,162,-1,-1,-1,-1]];
var toggle_ground;
var toggle_orientation;
var to_label = 9;
// hashsets --> rect per camera ? rect -> id to coordinates?
// store variables here? in db ? (reupload db?)
window.onload = function() {
  toggle_ground = true;
  toggle_orientation = true;

  var d = document.getElementById("changeF");
  if(d != null){
    d.className = d.className + " disabled";
    if(nblabeled >= to_label) {
      var button = document.getElementById("changeF");
      button.href="/gtm_hit/" + workerID + "/processFrame";
      button.text = "Finish";
    }
  }
  if (nblabeled > 0) {
    load_prev();
  }
  camName = cams.substring(2,cams.length-2).split("', '");
  for (var i = 0; i < cameras; i++) {
    boxes[i] = {};

    arrArray[i] = new Image();
    arrArray[i].id=("arrows"+i);
    arrArray[i].src = '../../static/gtm_hit/images/arrows'+i+'_3D.png';

    imgArray[i] = new Image();
    imgArray[i].id=(i+1);
    imgArray[i].onload = function() {
      var c = document.getElementById("canv"+this.id);
      var ctx = c.getContext('2d');

      ctx.drawImage(this,0,0);
      if(toggle_orientation)
        drawArrows(ctx,this.id-1);
      c.addEventListener('click',mainClick);
      loadcount++;
      if(loadcount == 7) {
        $("#loader").hide();
      }
      update();
    }

    loadcount = 0;
    $("#loader").show();
    imgArray[i].src = '../../static/gtm_hit/day_2/annotation_final/'+ camName[i]+ '/begin/'+frame_str+'.png'; // change 00..0 by a frame variable
    //imgArray[i].src = '../../static/gtm_hit/frames/'+ camName[i]+frame_str+'.png'; // change 00..0 by a frame variable
  }

  $(document).bind('keydown', "backspace",backSpace);
  $(document).bind('keydown', "left",left);
  $(document).bind('keydown', "right",right);
  $(document).bind('keydown', "up",up);
  $(document).bind('keydown', "down",down);
  $(document).bind('keydown', "tab",tab);
  $(document).bind('keydown', "space",space);
  $(document).bind( "keydown", "e",validate);
  $(document).bind( "keydown", "z",zoomControl);
  $(document).bind( "keydown", "t",toggleGround);
  $(document).bind( "keydown", "h",toggleOrientation);
  $("#pID").bind( "keydown", "return",changeID);
  $("#pID").val(-1);
  $("#pHeight").val(-1);
  $("#pWidth").val(-1);

};

function mainClick(e) {
  var canv = this;
  var offset = $(this).offset();
  var relativeX = (e.pageX - offset.left)-15;
  var relativeY = (e.pageY - offset.top);
  var xCorr = Math.round(relativeX*1920/(this.clientWidth-30));
  var yCorr = Math.round(relativeY*1080/this.clientHeight);
  if(relativeX >=0 && relativeX<=(this.clientWidth - 29)) {
    if(zoomOn)
      zoomOut();
    //post
    $.ajax({
      method: "POST",
      url: "click",
      data: {
        csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
        x: xCorr,
        y: yCorr,
        canv: this.id
      },
      dataType: "json",
      success: function(msg) {
        var rid = msg[0].rectangleID;
        var indof = rectsID.indexOf(rid);
        if(indof == -1) {
          rectsID.push(rid);
          chosen_rect = rectsID.length-1;
          while(personID in validation)
          personID++;
          identities[rid] = personID;
          validation[personID] = true;
          saveRect(msg,personID);
        } else {
          chosen_rect = indof;
        }
        update();
      }
    });

  }
}

function backSpace() {
  if (rectsID.length > 0){
    var rid = rectsID[chosen_rect];
    rectsID.splice(chosen_rect,1);
    var idPers = identities[rid];
    delete validation[idPers];
    delete identities[rid];
    //validation_dict.pop(idPers)
    //identities.pop(idRect)
    //for i in range(NB_PICTURES):
    //  if idPers in person_rect[i]:
    //    person_rect[i].pop(idPers)
    if (chosen_rect == rectsID.length) {
      chosen_rect--;
    }
    if(zoomOn) {
      zoomOut();
    }
    update();
  }
  return false;
}

function tab() {
  if (rectsID.length <= 1)
    return false;

  chosen_rect++;
  if(zoomOn)
    zoomOut();
  update();
  return false;

}

function space() {
  if (rectsID.length <= 1)
    return false;

  chosen_rect--;
  if(zoomOn)
    zoomOut();
  update();
  return false;
}

function left() {
  sendAJAX("move","left",rectsID[chosen_rect],moveRect);
  update();
  return false;
}

function right() {
  sendAJAX("move","right",rectsID[chosen_rect],moveRect);
  update();
  return false;
}

function up() {
  sendAJAX("move","up",rectsID[chosen_rect],moveRect);
  update();
  return false;
}

function down() {
  sendAJAX("move","down",rectsID[chosen_rect],moveRect);
  update()
  return false;
}

function incrWidth() {
  var ind = getIndx();
  var pid = identities[rectsID[chosen_rect]];
  var rect = boxes[ind][pid];
  rect.x1 = rect.x1-1;
  rect.x2 = rect.x2+1;
  boxes[ind][pid] = rect;

  var size = (rect.x2-rect.x1)*rect.ratio;
  updateSize(false,size,ind);
  return false;

}

function decrWidth() {
  var ind = getIndx();
  var pid = identities[rectsID[chosen_rect]];
  var rect = boxes[ind][pid];
  rect.x1 = rect.x1+1;
  if(rect.x2 - rect.x1 < 1) {
    rect.x1 = rect.x2 -1;
  } else {
    rect.x2 = rect.x2-1;
  }
  boxes[ind][pid] = rect;
  var size = (rect.x2-rect.x1)*rect.ratio;
  updateSize(false,size,ind);
  return false;

}

function incrHeight() {

  var ind = getIndx();
  var pid = identities[rectsID[chosen_rect]];
  var rect = boxes[ind][pid];
  rect.y1 = rect.y1-1;
  boxes[ind][pid] = rect;

  var size = (rect.y2-rect.y1)*rect.ratio;
  updateSize(true,size,ind);
  return false;

}

function decrHeight() {
  var ind = getIndx();
  var pid = identities[rectsID[chosen_rect]];
  var rect = boxes[ind][pid];
  rect.y1 = rect.y1+1;
  if(rect.y2 - rect.y1 < 1) {
    rect.y1 = rect.y2-1;
  }
  boxes[ind][pid] = rect;

  var size = (rect.y2-rect.y1)*rect.ratio;
  updateSize(true,size,ind);
  return false;
}

function getIndx() {
  var h = -1;
  var retInd = -1;
  var pid = identities[rectsID[chosen_rect]];
  for (var i = 0; i < cameras; i++) {
    r = boxes[i][pid];
    tpH = Math.abs(r.y1 - r.y2);

    if(tpH > h) {
      h = tpH;
      retInd = i;
    }
  }
  return retInd;
}

function updateSize(height,size,ind) {
  var r = rectsID[chosen_rect];
  var pid = identities[r];
  for (var i = 0; i < cameras; i++) {
    rect = boxes[i][pid];
    if(i != ind && rect.y1 != 0) {
      if(height) {
        var b = Math.round(rect.y2 - size/rect.ratio);
        if(rect.y2 - b < 1)
        b = rect.y2 - 1;
        rect.y1 = b;
      } else {
        var delta = size/(2*rect.ratio);
        var c = Math.round(rect.xMid + delta);
        var a = Math.round(rect.xMid - delta);
        if(c - a < 1)
        a = c - 1;
        rect.x1 = a;
        rect.x2 = c;
      }
    }
    boxes[i][pid] = rect;
  }
  update()
}

function save() {
  var dims = {};
  var k = 0;
  for (var i = 0; i < rectsID.length; i++) {
    var rid = rectsID[i];
    var pid = identities[rid];
    dims[rid] = [];
    dims[rid].push(pid);
    dims[rid].push(validation[pid]);
  }

  for (var i = 0; i < cameras; i++) {
    for (var j = 0; j < rectsID.length; j++) {
      var rid = rectsID[j];
      var pid = identities[rid];

      var field = boxes[i][pid];
      if(field.x2 != 0){
        dims[rid].push(field.x1);
        dims[rid].push(field.y1);
        dims[rid].push(field.x2);
        dims[rid].push(field.y2);
      } else {
        dims[rid].push(-1);
        dims[rid].push(-1);
        dims[rid].push(-1);
        dims[rid].push(-1);
      }
    }
  }
  $.ajax({
    method: "POST",
    url: 'save',
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      data: JSON.stringify(dims),
      ID: frame_str,
      workerID: workerID
    },
    success: function(msg) {
      console.log(msg);
    }
  });

}

function load() {
  loader('load');
}

function load_prev() {
  loader('loadprev');

}

function loader(uri) {

  $.ajax({
    method: "POST",
    url: uri,
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      ID: frame_str,
      workerID: workerID
    },
    dataType: 'json',
    success: function(msg) {
      clean();
      var maxID = 0;
      for (var i = 0; i < msg.length; i++) {
        var rid = msg[i][0].rectangleID;
        var indof = rectsID.indexOf(rid);
        if(indof == -1) {
          rectsID.push(rid);
          saveRectLoad(msg[i]);
          chosen_rect = rectsID.length-1;
          identities[rid] = msg[i][7];
          var pid = msg[i][7];
          if(pid > maxID)
            maxID = pid;
          if(uri == "loadprev")
            validation[pid] = false;
          else
            validation[pid] = msg[i][8];
        }
      }
      personID = maxID + 1;
      update();

    }
  });
}
function clean() {
  for (var i = 0; i < cameras; i++) {
    boxes[i] = {};
    rectsID = [];
    validation =  {};
    identities = {};
    personID = 0;
    chosen_rect = 0;
  }
  update();
}

function changeFrame(order,increment) {
  save();
  if(nblabeled >= to_label) {
    return true;
  }
  $.ajax({
    method: "POST",
    url: 'changeframe',
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      order: order,
      frameID: frame_str,
      incr: increment,
      workerID: workerID
    },
    dataType: "json",
    success: function(msg) {
      frame_str = msg['frame'];
      nblabeled = msg['nblabeled'];
      if(nblabeled >= to_label) {
        var button = document.getElementById("changeF");
        button.href="/gtm_hit/" + workerID + "/processFrame";
        button.text = "Finish";
      }
      loadcount = 0;
      $("#loader").show();
      fstr = frame_str;
      fstr = fstr.replace(/^0*/, "");
      $("#frameID").html("Frame ID: " + fstr +"&nbsp;&nbsp;");
      for (var i = 0; i < cameras; i++)
        imgArray[i].src = '../../static/gtm_hit/day_2/annotation_final/'+ camName[i]+ '/begin/'+frame_str+'.png'; // change 00..0 by a frame variable
        //imgArray[i].src = '../../static/gtm_hit/frames/'+ camName[i]+frame_str+'.png'; // change 00..0 by a frame variable

    },
    complete: function() {
      load_prev();
    }
  });

}

function next() {
  changeFrame('next',1);
}

function prev() {
  changeFrame('prev',1);
}

function nextI() {
  changeFrame('next',10);
}

function prevI() {
  changeFrame('prev',10);
}

function validate() {
  var rid = rectsID[chosen_rect];
  var idPers = identities[rid];
  validation[idPers] = true;
  return false;
}

function changeID() {
  var newID = parseInt($("#pID").val());
  if (rectsID.length > 0 && newID >= 0) {
    var rid = rectsID[chosen_rect];
    var pid = identities[rid];
    var match = false;
    for (key in identities) {
      if (identities[key] == newID)
        match = true;
    }
    if(!match) {
      validation[newID]= validation[pid];
      delete validation[pid];
      identities[rid] = newID;
      for(key in boxes){
        if(pid in boxes[key]){
          var args = boxes[key][pid];
          boxes[key][newID] = args;
          delete boxes[key][pid];
        }
      }
      $("#pID").val(newID);
    } else {
      $("#pID").val(pid);
    }
  }
}

function sendAJAX(uri,data,id,suc) {
  $.ajax({
    method: "POST",
    url: uri,
    data: {
      csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value,
      data: data,
      ID: id
    },
    dataType: "json",
    success: function(msg) {
      if(msg.length > 0)
        suc(msg,id);
      update();
    }
  });
}

function saveRect(msg,pid) {
  for (var i = 0; i < msg.length; i++) {
    var ind = msg[i].cameraID;
    boxes[ind][pid] = msg[i];
  }
}

function saveRectLoad(msg) {
  for (var i = 0; i < msg.length-2; i++) {
    var ind = msg[i].cameraID;
    boxes[ind][msg[7]] = msg[i];
  }
}

function moveRect(msg,id) {
  var pid = identities[id];
  if(typeof boxes[0][pid] == "undefined") {
    return false;
  }
  var index = rectsID.indexOf(id);
  var nextRect = msg[0].rectangleID;
  rectsID.splice(index,1);
  rectsID.push(nextRect);
  chosen_rect = rectsID.length-1;
  identities[nextRect] = pid;
  delete identities[id];
  validation[pid] = true;

  for (var i = 0; i < msg.length; i++) {
    var f = msg[i];
    var ind = f.cameraID;
    var oldRect = boxes[ind][pid];

    var newRect = msg[i];
    var heightR = Math.abs(oldRect.y1-oldRect.y2)*oldRect.ratio;
    var widthR = Math.abs(oldRect.x1-oldRect.x2)*oldRect.ratio;

    if(newRect.ratio > 0){
      newRect.y1 = Math.round(newRect.y2 - (heightR/newRect.ratio));
      var delta = widthR/(2*newRect.ratio);
      newRect.x2 = Math.round(newRect.xMid + delta);
      newRect.x1 = Math.round(newRect.xMid - delta);
    }
    boxes[ind][pid] = newRect;
  }
}

function update() {
  chosen_rect = ((chosen_rect % rectsID.length) + rectsID.length) % rectsID.length;
  $("#pID").val(identities[rectsID[chosen_rect]]);

  drawRect();
  if(toggle_ground)
    drawGround();

  var d = document.getElementById("changeF");
  if(d!=null) {
    if (rectsID.length > 1) {
      if(checkRects())
        d.className = d.className.replace(" disabled","");
        else if(d.className.indexOf("disabled") == -1)
        d.className = d.className + " disabled";
    } else if(d.className.indexOf("disabled") == -1) {
      d.className = d.className + " disabled";
    }
  }
}

function drawRect() {
  for (var i = 0; i < cameras; i++) {
    var c = document.getElementById("canv"+(i+1));
    var ctx=c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.drawImage(imgArray[i],0,0);
    if(toggle_orientation)
      drawArrows(ctx,i);
  }
  var heightR = 0;
  var widthR = 0;
  var sumH = 0;
  for (key in boxes) {
    for (var r = 0; r < rectsID.length; r++) {
      var field = boxes[key][identities[rectsID[r]]];
      if(field.y1 != -1 && field.y2 != -1 && field.x1 != -1) {
        var c = document.getElementById("canv"+(field.cameraID+1));
        var ctx=c.getContext("2d");
        var w = field.x2 - field.x1;
        var h = field.y2 - field.y1;
        if(r == chosen_rect) {
          ctx.strokeStyle="cyan";
          ctx.lineWidth="7";
          heightR += (field.y2-field.y1)*field.ratio;
          widthR += (field.x2-field.x1)*field.ratio;
          sumH += 1;
        } else {
          var pid = identities[field.rectangleID];
          if(validation[pid])
            ctx.strokeStyle="white";
          else
            ctx.strokeStyle="yellow";
          ctx.lineWidth="4";
        }
        ctx.beginPath();
        ctx.rect(field.x1,field.y1,w,h);
        ctx.stroke();
        ctx.closePath();

        ctx.beginPath();
        ctx.fillStyle = "red";
        ctx.fillRect(field.xMid-5,field.y2-5,10,10);
        ctx.stroke();
        ctx.closePath();

      }
    }
  }
  if(chosen_rect >= 0) {
    $("#pHeight").text(Math.round(heightR/sumH));
    $("#pWidth").text(Math.round(widthR/sumH));
  } else {
    $("#pHeight").text(-1);
    $("#pWidth").text(-1);
  }

}

function drawGround() {
  for (var i = 0; i < cameras; i++) {
    var c = document.getElementById("canv"+(i+1));
    var ctx=c.getContext("2d");
    ctx.strokeStyle="chartreuse";
    ctx.lineWidth="2";
    ctx.beginPath();

    ctx.moveTo(bounds[i][0], bounds[i][1]);
    for (var j = 2; j < bounds[i].length; j=j+2) {
      if(bounds[i][j] >= 0) {
        ctx.lineTo(bounds[i][j], bounds[i][j+1]);
      }
    }
    ctx.stroke();
    ctx.closePath();

  }
}

function drawArrows(ctx, idx) {
  ctx.drawImage(arrArray[idx],0,0);
}

function zoomControl() {
  if(rectsID.length > 0){
    if(!zoomOn) {
      zoomIn();
    } else {
      zoomOut();
    }

  }
  update();
}

function zoomIn() {
  for (var i = 0; i < cameras; i++) {
    var pid = identities[rectsID[chosen_rect]];
    var r = boxes[i][pid];

    var c = document.getElementById("canv"+(i+1));

    zoomratio[i] = c.height*60/(100*(r.y2-r.y1));
    if(zoomratio[i] != Infinity) {

      var ctx = c.getContext('2d');
      c.width=c.width/zoomratio[i];
      c.height=c.height/zoomratio[i];
      var originx = r.xMid - c.width/2;
      // var originx = r.xMid;
      var originy = r.y1-12.5*c.clientHeight/100;
      // ctx.scale(1.75,1.75);
      ctx.translate(-originx, -originy);

    }
  }
  zoomOn = true;
  return false;

}

function zoomOut() {
  for (var i = 0; i < cameras; i++) {
    var c = document.getElementById("canv"+(i+1));
    if(zoomratio[i] != Infinity) {
      c.width=c.width*zoomratio[i];
      c.height=c.height*zoomratio[i];
    }
  }
  zoomOn = false;
  return false;
}

function toggleGround() {
  if(toggle_ground == false)
    toggle_ground = true;
  else
    toggle_ground=false;
  update();
  return false;
}

function toggleOrientation() {
  if(toggle_orientation == false)
    toggle_orientation = true;
  else
    toggle_orientation=false;
  update();
  return false;
}

function checkRects() {
  var c = 0;
  for (var i = 0; i < rectsID.length; i++) {
    var personID = identities[rectsID[i]];
    if(validation[personID])
      c++;
  }
  if(c > 1)
    return true;
  else
    return false;
}
