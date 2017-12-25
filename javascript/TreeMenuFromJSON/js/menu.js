$(document).ready(function(){
	getMenuData(function(data){	
		if (typeof data === "string")
			var navigation = $.parseJSON(data).navigation;
		else
			var navigation = data.navigation;
		buildMenu(navigation);
	});
});

function getMenuData(callback) {
	return $.ajax({
		url: "data/menu_data.json",
		success: function (data) {
			if (typeof callback === "function")
				callback(data);
		}
	});
}

function buildMenu(navigation) {
	$("#treecontrol").after(buildList(navigation));
	$("#red").treeview({
		animated: "fast",
		collapsed: true,
		control: "#treecontrol"
	});
	function buildList(navigation) {
		var nav_html = "";
		for (var i = 0; i < navigation.length; i++) {
			var id = navigation[i]['id'];
			var className = navigation[i]['class'];
			var label = navigation[i]['label'];
			var labelClass = navigation[i]['labelClass'];
			var link = navigation[i]['link'];
			var target = navigation[i]['target'];
			var submenu = navigation[i]['navigation'];
			var id_class_str = "";
			var label_str = "";
			var target_str = "";

			if (typeof(id) != "undefined")
				id_class_str += " id='" + id + "'";
			if (typeof(className) != "undefined") 
				id_class_str += " class='" + className + "'";
			if (typeof (labelClass) != "undefined") 
				label_str = " class='" + labelClass + "'";
			if (typeof (target) != "undefined")
				target_str = " target='" + target + "'";
			if (typeof(link) != "undefined") 
				nav_html += '<li' + id_class_str + '><span' + label_str + '><a href="' + link + '"' + target_str + '>' + label + '</span></a>'; 
			else
				nav_html += '<li' + id_class_str + '><span' + label_str + '>' + label + '</span>'; 

			if( typeof(submenu) != "undefined" ){
				nav_html += '<ul>';
				nav_html += buildList(submenu); 
				nav_html += '</ul>';
			}
			nav_html += '</li>';
		}
		return nav_html;
	}
}
