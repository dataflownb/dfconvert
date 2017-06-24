define([
	"require",
	"jquery",
	"base/js/namespace"], 
	function(require,$, Jupyter){
	
	$("#file_menu").append("<li class='divider'></li>")
	$("#file_menu").append("<li id='imp_dfpy'><a href='#'>Import from Dataflow Kernel</a></li>")
	$("#file_menu").append("<li id='exp_dfpy'><a href='#'>Export to Dataflow Kernel</a></li>")
	


	//console.log($('body').attr('data-notebook-path'))


	
	$('#imp_dfpy').click(function () {
		console.log("Import")
		$.get("../nbextensions/dfipy_convert/import.py",).done(function(data) { 
		data = "filename = '" + window.document.body.dataset.notebookName + "'\n" + data
		console.log(data)
		Jupyter.notebook.kernel.execute(data);
		console.log("Success");});
			
		});

	$('#exp_dfpy').click(function () {
			console.log("Export")
			$.get("../nbextensions/dfipy_convert/export.py",).done(function(data) { 
			data = "filename = '" + window.document.body.dataset.notebookName + "'\n" + data
			console.log(data)
			Jupyter.notebook.kernel.execute(data);
			console.log("Success");});
		});	

})

