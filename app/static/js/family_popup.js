/*!
 * Method for displaying Family information as popup-window
 */

function showPopup(id) {
	// When the user clicks on div, open the popup window
    var popup = document.getElementById("popup");
    console.log("showPopup for person "+id);
    popup.classList.toggle("show");
    //TODO: Find person families first
    vm.getFamilies(id);
  }
function away() {
	// When the user clicks on div, close the popup windoe
    var popup = document.getElementById("popup");
    console.log("showPopup close");
    popup.classList.toggle("show");
}

function parseSortname(name) {
	// Returns [surname,firstname,patronyme]
    return name.split("#");
  }
  
function htmlSortname(name) {
    // Parses a sortname to html representation
    var a = name.split('#');
    if (a.length != 3)  return name;
    return a[1]+" <i>"+a[2]+"</i> <b>"+a[0];
  }

function datesStr(dates,first=false) {
	// Parses a DateRange list format object (<int>, <str> [,<str>])
	if (!dates) return '';
    if (dates.length < 2) return '';
    if (first) return dateLocal(dates[1]);
    if (dates.length == 3) {
        return dateLocal(dates[1]) + ' ... ' + dateLocal(dates[2]);
    } else return dateLocal(dates[1]);
    return name.split("#");
  }

function dateLocal(date) {
    // Parses ISO style date 1820-12-03 to local 3.12.1820
    var a = date.split('-');
    if (a.length == 1) return date;
    if (a[1].startsWith('0'))   a[1] = a[1].substr(1,1);
    if (a.length == 2) return a[1]+'.'+a[0];
    if (a[2].startsWith('0'))   a[2] = a[2].substr(1,1);
    if (a.length == 3) return a[2]+'.'+a[1]+'.'+a[0];
    return "?"
  }

var vm = new Vue({
	   el: '#popup_app',
	   delimiters: ['${', '}'],
	   data: {
	     message: 'Not yet run',
	     person_uuid: '459d19f508b04865b333954c304313b7', //'paste here',
	     uuid: '?',
	     families: [],
	     currentId: 0,
	     status: '',
	     isShow: false
	   },
	   computed: {
	  		 current: function () {
	  			 // currentId = 1,2,...
	  			 if (vm.currentId <= vm.families.length && vm.currentId > 0)
	  				 return vm.families[vm.currentId-1];
	  			 console.log("false currentId "+ vm.currentId);
	  			 return false;
	  		    }
	   },
	   methods: {
		   changeFamily(index) {
			   // No 0 (=false) is allowed in currentId
	           console.log("changeFamily: katsotaan "+vm.families[index].id);
	           vm.currentId = index+1;
			},

//			away() {
//				// When the user clicks on div, close the popup windoe
//			    var popup = document.getElementById("popup");
//			    console.log("away hidden = "+popup.hidden);
//			    popup.hidden = true;
//			    console.log("away hidden = "+popup.hidden);
//			    //popup.classList.toggle("show");
//			},

		   getFamilies(q_uuid) {
			   // Asks for data for all families of given person
	           console.log("family for person "+q_uuid);
		       axios.post("/scene/json/families", {uuid:q_uuid})
		            .then (function(rsp, q_uuid) {
		            	   vm.families = [];
		    			   vm.status = "Status code: "+String(rsp.status);
	                       //console.log("stk result: "+rsp.data.statusText);
	                       vm.message=rsp.data.statusText;
	                       if (rsp.data.records.length == 0) {
	                    	   vm.families=[];
	                    	   return;
	                       }
	                       for (rec of rsp.data.records) {
	                           //console.log(rec);
	                    	   var fam = {};
	                    	   if (rec) {
	                               fam.id = rec.id;
	                               fam.rel_type = rec.rel_type;
	                               fam.dates = datesStr(rec.dates, first=true);
	                               fam.role = rec.role;
	                               fam.href = "/scene/family?uuid="+rec.uuid;
	                               fam.parents = [];
	                               fam.children = [];
	                               fam.title = "Perhe "+fam.id;

	                               for (parent of rec.parents) {
	                                   var p = {};
	                                   p.uuid = parent.uuid;
	                                   if (p.uuid == q_uuid) {
	                                	   p.is_self = "itse";
	                                       p.name = ['','',''];
	                                   } else {
	                                       p.name = parseSortname(parent.sortname);
	                                       p.is_self = "";
	                                   }
	                                   p.role = parent.role;
	                                   //if (p.role == 'father')  vm.father_name = p.name;
	                                   //else                     vm.mother_name = p.name;
	                                   p.href = "/scene/person?uuid="+parent.uuid
	                                   p.birth = datesStr(parent.dates, first=false);
	                                   fam.parents.push(p);
	                               }
	                               var gentext = ['Lapsi','Poika','Tytär'];
	                               for (child of rec.children) {
	                                   fam.has_children = true;
	                                   var c = {uuid:child.uuid};
	                                   if (c.uuid == q_uuid) {
	                                	   c.is_self = "itse";
	                                	   c.name = ['','',''];
	                                   } else {
	                                       c.name = parseSortname(child.sortname);
	                                       c.is_self = "";
	                                   }
	                                   c.href = "/scene/person?uuid="+child.uuid
	                                   c.gender = gentext[child.sex];
	                                   c.birth = datesStr(child.dates, first=false);
	                                   fam.children.push(c);
	                               }
	                               vm.families.push(fam);
	                    	   }
	                       }
	                       vm.changeFamily(0);
	    			 })
	   	   }
	  }
	})