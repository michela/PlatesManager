<?xml version="1.0" encoding="ISO-8859-1"?><!-- DWXMLSource="incomingplates.xml" --><!DOCTYPE xsl:stylesheet  [
	<!ENTITY nbsp   "&#160;">
	<!ENTITY copy   "&#169;">
	<!ENTITY reg    "&#174;">
	<!ENTITY trade  "&#8482;">
	<!ENTITY mdash  "&#8212;">
	<!ENTITY ldquo  "&#8220;">
	<!ENTITY rdquo  "&#8221;"> 
	<!ENTITY pound  "&#163;">
	<!ENTITY yen    "&#165;">
	<!ENTITY euro   "&#8364;">
]>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html" encoding="ISO-8859-1" doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN" doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"/>
<xsl:template match="/">

<html xmlns="http://www.w3.org/1999/xhtml">
<head>

<script type="text/javascript" src="/js/jquery.ui-1.5b4/jquery-1.2.4b.js"></script>
<script type="text/javascript" src="/js/jquery.ui-1.5b4/ui.core.js"></script>
<script type="text/javascript" src="/js/jquery.ui-1.5b4/ui.tabs.js"></script>
<link href="plates.css" type="text/css" rel="stylesheet" />
<link rel="stylesheet" href="/js/themes/flora/flora.all.css" type="text/css" media="screen" title="Flora (Default)" />
<link rel="stylesheet" href="/js/demos/css/style.css" type="text/css" />

<title><xsl:value-of select="plates/project"/> plates</title>
<script type="text/javascript">
//<![CDATA[
function clean(name) {
// escape chars which interfere with jquery
		name = name.replace(/\./g, '\\.');
		name = name.replace(/\_/g, '\\_');
		name = name.replace(/\//g, '\\/');
		return name;
} 


$(document).ready(function() {
	//alert('got here');
	 $('.confirmdelete').hide();
	 $('.shareTemplate').hide();
	 $('.prompt').hide();
	 //$('.share').attr('disabled','disabled'); // to hide SHARE button 
	 //$('.ok').attr('disabled','disabled');	// to hide PUBLISH button
	// $('.thumbnail').shadow();
	//$('#all > ul').tabs();
	
});

	
$(window).bind('load', function() {
	$('#container-1 > ul').tabs();
	$("#ftp").load("/update/ftp");
});
  
$(function() {
	
	
	function showLoading(element) {
		var loader = "<img class='ajaxloader' src='/static/images/ajax-loader.gif' />";
		$(element).html(loader);
		$(element).show();
		//pause(1000);  // why not working??
	}
	
	$('a.ftp').click(function() {
//		alert("/update/ftp?remoteDir=" + $(this).attr('name'));
		$('#container-1 > ul').tabs('select','#ftp');
		$("#ftp").load("/update/ftp?remoteDir=" + $(this).attr('name'));
		return false;
    });

	$('input.share').click(function(){
		var p = 'testing ';	
		var path = $(this).attr('id');
		path = path.substr(5);
		$('#msgShare').text("Re. SHOT " + path + "\n\n");
		//alert('sharing this');
		element = clean('#prompt' + path);
		$(this).attr('disabled','disabled');
		//alert($('.shareTemplate').html());
		//$(element).html('testing');
		$(this).parents().next().next().next('.prompt').html($('.shareTemplate').html());
		shareButton = $(this);
		sharePrompt = $(this).parents().next().next().next('.prompt');
		$(".shareTemplate").css('color','green');
	  
		
		
		$('input.sendShare').click(function(){
	
			var nameAddr  = $("#fromShare").val();
			var toAddr = $("#toShare").val();
			var msg = $('#msgShare').val();
			var subject = "SHOT " + path;
			var fromAddr = "modfilms.net <reception@modfilms.net>";
      		msg = msg.replace(/\n/g, "%0A");
			//alert (msg);
			if ($("#fromShare").val().length == 0 || $("#toShare").val().length == 0) {
				//alert('Invalid input');
				$('#promptShare').css('color','red');
				$('#promptShare').html(' You need to fill in all fields');
				$('#promptShare').show();
			}
			else {
				$(sharePrompt).html("<p><img class='ajaxloader' src='/static/images/ajax-loader.gif' /></p>");
				var fromPage = '/plates';
				
				//var url = "/update/ftpmon/emailer?fromPage=" + fromPage + "&name=" + nameAddr + "&fromAddr=" + fromAddr + "&toAddr=" + toAddr + "&subject=" + subject + "&msg=" + msg + "&jsoncallback=?";
				var url = "/update/ftpmon/emailer?jsoncallback=?";
				$.post(url, {fromPage:fromPage, name:nameAddr,fromAddr:fromAddr,toAddr:toAddr,subject:subject,msg:msg}, function(data) {	
					var tprompt = sharePrompt;
					if (data.good == true) {
						$(tprompt).css('color','green');
						$(tprompt).html(data.err);
						$(tprompt).show();
						$(tprompt).css('color','green');
					}
					else {
						$(tprompt).css('color','red');
						$(tprompt).html(data.err);
						$(tprompt).show();
						$(shareButton).removeAttr('disabled');  
					}
				}, 'json');
				$(sharePrompt).empty();	
				$(shareButton).removeAttr('disabled');  	
			}
			return false;
		});
		
		$('input.cancelShare').click(function(){
			$(sharePrompt).empty();
			$(shareButton).removeAttr('disabled');  
			return false;
		});
	
		$(this).parents().next().next().next('.prompt').css('color','red');
		$(this).parents().next().next().next('.prompt').show();
		return false;
	});
	
	$('input.ok').click(function(){
		var path = $(this).attr('id');
		path = path.substr(2);
		var url = "/update/ftpmon/publish?path=" + path + "&jsoncallback=?";
		element = clean('#prompt' + path);
		//alert(element);
		showLoading(element);
       	var p = 'Shot published to tracker.';
		//$(this).parents().next().next().next('.prompt').html(p);
		$(element).html(p);
		$(element).css('color','green');
		$(element).show();
		$("#masterprompt").hide();
		$.getJSON(url, function(data){	
				//alert(path);
				var tprompt = "#prompt" + path;
				tprompt = clean(tprompt);
				var status = "#gallery" + path;
				status = clean(status);
				
				if (data.good == true) {
					//alert(data.good + ' ' + data.err);
					$(tprompt).css('color','green');
					$(tprompt).html(data.err);
					$(tprompt).show();
					$(status).css('color','green');
					//alert(tprompt);
					//$("#master").html(data.err);
					//$(this).parents().next().next().next('.prompt').html(data.err);
					//$(this).parents().next().next().next('.prompt').css('color','green');
					//$(this).parents().next().next().next('.prompt').show();
				}
				else {
					//alert(data.good + ' ' + data.err);
					$(tprompt).css('color','red');
					//var err = "Redo already in progress... ";
					$(tprompt).html(data.err);
					$(tprompt).show();
					//$(this).parents().next().next().next('.prompt').html(data.err);
					//$(this).parents().next().next().next('.prompt').css('color','red');
					//$(this).parents().next().next().next('.prompt').show();
				}
			}
		);
		return false;
    });
	$('input.redo').click(function(){
	
		var path = $(this).attr('id');
		path = path.substr(4);
		var p = 'The proxy video has been deleted. A new one will be created from the available image sequence. An email alert will be sent when this is done.';		
		var url = "/update/ftpmon/redo?path=" + path + "&jsoncallback=?";
		//showLoading("#prompt" + path);
		element = clean('#prompt' + path);
		showLoading(element);
		$(this).attr('disabled','disabled');
	
		$("#masterprompt").hide();
				
		$.getJSON(url, function(data){	
				//alert(path);
	
				var tprompt = "#prompt" + path;
				tprompt = clean(tprompt);
				var status = "#gallery" + path;
				status = clean(status);
				
				if (data.good == true) {
					//alert(data.good + ' ' + data.err);
					$(tprompt).css('color','green');
					$(tprompt).html(p);
					$(tprompt).show();
					$(status).css('color','green');
					showLoading(status);
					$(status).show();
					//alert(tprompt);
					//$("#master").html(data.err);
					//$(this).parents().next().next().next('.prompt').html(data.err);
					//$(this).parents().next().next().next('.prompt').css('color','green');
					//$(this).parents().next().next().next('.prompt').show();
				}
				else {
					//alert(data.good + ' ' + data.err);
					$(tprompt).css('color','red');
					var err = "Redo already in progress... ";
					$(tprompt).html(err);
					$(tprompt).show();
					//$(this).parents().next().next().next('.prompt').html(data.err);
					//$(this).parents().next().next().next('.prompt').css('color','red');
					//$(this).parents().next().next().next('.prompt').show();
				}
			}
		);
		return false;
	});
	$('input.ftp').click(function(){
	//	alert("/update/ftp?remoteDir=" + this.name);
		$('#container-1 > ul').tabs('select','#ftp');
		$("#ftp").load("/update/ftp?remoteDir=" + this.name);
		return false;
	});
	$('input.delete').click(function(){
		//alert('got here');
		$(this).parents('.deleteall').hide();
		var p = 'This action deletes all files for this sequence. It cannot be undone. Confirm you wish to proceed.';		
		$(this).parents().next().next('.prompt').html(p);
		$(this).parents().next().next('.prompt').css('color','red');
		$(this).parents().next().next('.prompt').show();
		$(this).parents().next('.confirmdelete.').show();
		$("#masterprompt").hide();
		return false;
    });
	$('input.okdelete').click(function(){
		//alert('got here');
		var p = 'All files scheduled for deletion... this index will be rebuilt...';
		var path = $(this).attr('id');
		path = path.substr(8);
		var url = "/update/ftpmon/delete?path=" + path + "&jsoncallback=?";	
		thepath = path;
		path = clean(path);
		showLoading(path);
		//alert(path);
		var confirmdelete = "#confirmdelete" + path;
		var tprompt = "#prompt" + path;
		var deleteall = "#deleteall" + path;
		var row = "#row" + path;
		//alert(url);
		$.getJSON(url, function(data){
			//alert('got here, row is ' + row);
			if (data.good == true) {
				$(row).hide();
				$("#masterprompt").html(thepath + " deleted");
				$("#masterprompt").css('color','green');
				$("#masterprompt").show();
				$(row).hide();
			}
			else {
				$(tprompt).css('color','red');
				$err = "";
				$(tprompt).html(err + data.err);
				$(tprompt).show();
				$(confirmdelete).hide();
				$(deleteall).show();
			}
			}
		);
		return false;
    });
	$('input.canceldelete').click(function(){
	//alert('got here');
	$(this).parents().next('.prompt').hide();
	$(this).parents().parents('.confirmdelete').hide();
	$(this).parents().parents().prev('.deleteall').show();
	return false;
    });
});
//]]> 
</script>
</head>
<body class="flora">
<div id="masterprompt"></div>
<h1><a name="incomingplates" id="incomingplates"><xsl:value-of select="plates/project"/> plates</a></h1>

        <div id="container-1">
            <ul>
                <li><a href="#fragment-1"><span>/iaa/inbound</span></a></li>
                <li><a href="#fragment-2"><span>/iaa/outbound</span></a></li>
                <li><a href="#ftp"><span>FTP</span></a></li>
                <li><a href="#fragment-4"><span>Help</span></a></li>
            </ul>

 <div id="fragment-1">
		<form action="" method="post" enctype="multipart/form-data" name="form1" id="form1">
		  <table class="incoming_plates" border="1" width="1142">
		<tr>
		<th width="430">PLATES</th>
		<th width="206">STATUS / PREVIEW </th>
		<th width="484">ACTIONS</th>
		</tr>
		<xsl:for-each select="plates/job[folder='/iaa/inbound']">
		<tr id="row{id}">
			<td><p class="style7"><a name="{ftpDir}" class="ftp" href="#"><xsl:value-of select="id"/></a></p>
			  <p class="style10"><xsl:value-of select="framesLength"/> frames (<xsl:value-of select="startFrame"/> - <xsl:value-of select="endFrame"/>)</p>
			  <!-- <p class="style10"><xsl:value-of select="lastModified"/></p>--> </td> 
			<td>
				<xsl:if test="status = &quot;upload complete&quot;">
				<div id="gallery{id}"><p><a class="gallery" href="{videoURL}"><img class="thumbnail" border="0" width="198" src="{thumbnailURL}" alt="thumbnail" /></a></p></div>
				</xsl:if>
				<xsl:if test="status != &quot;upload complete&quot;">
				<p id="status{id}" class="style8"><xsl:value-of select="status"/></p>
				</xsl:if>
			</td>
			<td>
			  <p>
			    <input id="share{id}" class="share" value="SHARE" type="submit"   />
			    <input id="ok{id}" class="ok" value="PUBLISH" type="submit" />
			   <input id="redo{id}" class="redo" value="REDO QUICKTIME" type="submit" />
			   <input class="ftp" name="{ftpDir}" value="GO TO FTP" type="submit" />
			   </p>
			  <div id="deleteall{id}" class="deleteall"><input class="delete" value="DELETE ALL FILES" type="submit" /></div>
			  <div id="confirmdelete{id}" class="confirmdelete"><p><input id="okdelete{id}" class="okdelete" value="CONFIRM DELETE ALL FILES" type="submit" /> or <input class="canceldelete" value="CANCEL" type="submit" /></p></div>
			  <div id="prompt{id}" class="prompt"></div>
			</td>
		</tr>
		</xsl:for-each>
		</table>
		</form>
</div>
 <div id="fragment-2">
		<form action="" method="post" enctype="multipart/form-data" name="form1" id="form1">
		  <table class="incoming_plates" border="1" width="1142">
		<tr>
		<th width="430">PLATES</th>
		<th width="206">STATUS / PREVIEW </th>
		<th width="484">ACTIONS</th>
		</tr>
		<xsl:for-each select="plates/job[folder='/iaa/outbound']">
		<tr id="row{id}">
			<td><p class="style7"><a name="{ftpDir}" class="ftp" href="#"><xsl:value-of select="id"/></a></p>
			  <p class="style10"><xsl:value-of select="framesLength"/> frames (<xsl:value-of select="startFrame"/> - <xsl:value-of select="endFrame"/>)</p>
			  <!-- <p class="style10"><xsl:value-of select="lastModified"/></p>--> </td> 
			<td>
				<xsl:if test="status = &quot;upload complete&quot;">
				<div id="gallery{id}"><p><a class="gallery" href="{videoURL}"><img class="thumbnail" border="0" width="198" src="{thumbnailURL}" alt="thumbnail" /></a></p></div>
				</xsl:if>
				<xsl:if test="status != &quot;upload complete&quot;">
				<p id="status{id}" class="style8"><xsl:value-of select="status"/></p>
				</xsl:if>
			</td>
			<td>
			  <p>
			    <input id="share{id}" class="share" value="SHARE" type="submit"   />
			    <input id="ok{id}" class="ok" value="PUBLISH" type="submit" />
			   <input id="redo{id}" class="redo" value="REDO QUICKTIME" type="submit" />
			   <input class="ftp" name="{ftpDir}" value="GO TO FTP" type="submit" />
			   </p>
			  <div id="deleteall{id}" class="deleteall"><input class="delete" value="DELETE ALL FILES" type="submit" /></div>
			  <div id="confirmdelete{id}" class="confirmdelete"><p><input id="okdelete{id}" class="okdelete" value="CONFIRM DELETE ALL FILES" type="submit" /> or <input class="canceldelete" value="CANCEL" type="submit" /></p></div>
			  <div id="prompt{id}" class="prompt"></div>
			</td>
		</tr>
		</xsl:for-each>
		</table>
		</form>
</div>
<div class="shareTemplate">
<table width="100" border="0">
  <tr>
    <td>FROM:</td>
    <td><input id="fromShare" type="text" value="" size="40"/></td>
  </tr>
  <tr>
    <td>TO: </td>
    <td><input id="toShare" type="text" value="" size="40"/></td>
  </tr>
  <tr>
    <td>MESSAGE: </td>
    <td><textarea cols="40" rows="5" id="msgShare"></textarea></td>
  </tr>
</table>
<p>
  <input id="sendShareButton" type="submit" class="sendShare" value="SEND" />
or
<input id="cancelShareButton" type="submit" class="cancelShare" value="CANCEL" /><span id="promptShare"></span>
</p>
</div>
 <div id="ftp">

 </div>
 <div id="fragment-4">
 
              <h1>Plates Manager</h1>
              <p>This system provides FTP site monitoring and a simple web interface to help manage the volume of files associated with image sequences.</p>
              <h2><br />
                How to use </h2>
              <p> * Follow the upload process paying particular attention to the naming convention for files and file format requirements. </p>
              <h2>Support issues </h2>
              <p> * Contact your StudioAdministrator if you have any problems. </p>
              <h2>Features </h2>
              <h3>Automatic features </h3>
              <p> * Invalid files are automatically deleted<br />
                * Sequences are checked for gaps and invalid files<br />
                * Quicktime and thumbnail image previews are generated (in a standard format) - click on thumbnail to play video<br />
                * Alert notifications are sent </p>
              <h3>Manual features </h3>
              <ul>
                <li> SHARE - prompt to email a link to one or more email addresses</li>
                <li>PUBLISH - one-click publishing facility after manual checks are done. Same as if Quicktime preview image is uploaded to the Render tracker</li>
                <li>REDO QUICKTIME - deletes and re-creates Quicktime. Useful when upload errors occur or sequence uploaded in stages</li>
                <li>DELETE ALL FILES - removes all plates for a render</li>
                <li>GO TO FTP - browse FTP directory via HTTP </li>
              </ul>
</div>
</div>
</body>
</html>

</xsl:template>
</xsl:stylesheet>
