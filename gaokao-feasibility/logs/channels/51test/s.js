//PC_SHOW
function doZoom(size) {
    var zoom = document.all ? document.all['content-txt'] : document.getElementById('content-txt');
    zoom.style.fontSize = size + 'px';
}

var is_class = false;
if (typeof(class_url) != "undefined" && class_url != "") {
    is_class = true;
}

var strVarViewURL = "https://user.51test.net/vip/download/word/?id=" + str_articleid+"&classid=" + str_classid+"&nclassid=" + str_nclassid+"&nkey=" + str_nkey+"&is_downloadurl=" + is_downloadurl;

function a(id) {
    switch (id) {
        case "show_title":
			if (is_class&&str_classid!=1) {
				document.writeln("<script  src=\'//js.wykw.com/js_new/b/miaoshu_kc.js\'></script>");
			}
            break;
			
        case "show_conten1":
            if (!is_vip) {
                document.writeln("<div style=\'margin: 0 auto;width: 100%;margin-bottom: 10px;margin-top: 15px;\'><script  src=\'//js.wykw.com/js_new/show_content_vip_pro.js\'></script></div>");
            }
            if (is_class&&str_classid!=1) {
                document.writeln("<div class=\'article-show-content-jieshao-kc\'><script src=\'//js.wykw.com/js_new/b/show_bottom_kc.js\'></script></div>");
            }			
            break;
			
        case "show_conten2":
            document.writeln("<script  src=\'//js.wykw.com/js_new/b/show_mzsm.js\' ></script>");
            break;
			
        case "show_right1":
			
            if (is_class) {
                document.writeln("<script  src=\'//js.wykw.com/js_new/b/right_kc.js\' ></script>");
            } else {
                if (!is_vip) {
                    document.writeln("<div style=\'margin:20px 0px 20px 0px;\' ><div class=\'s_r_img\'>");
                    document.writeln("<a href=https://www.51test.net/vip/ target=_blank ><span><h2>VIP会员尊享特权！</h2></span></a>");
                    document.writeln("<div class=\'Course\'><a href=https://user.51test.net/tiku/?siteid=" + str_url + " target=\'_blank\' class=\'vip\'>免费题库</a><a href=" + strVarViewURL + " target=\'_blank\' class=\'mfst\'>文档下载</a></div></div></div>");
                }
            }

			if(str_classid<16){
				document.writeln("<div style=\'margin:10px 0px 20px 0px;\' class=\'ads\'><a href=https://user.51test.net/tiku/?siteid="+ str_url +"  target=_blank><img src=https://img.wykw.com/vip/vip_tiku.jpg width=300 height=250></a></div>");
			}
			else{
				if (!is_vip) {
					document.writeln("<div style=\'margin:10px 0px 20px 0px;\' class=\'ads\'><a href=https://www.51test.net/vip/  target=_blank><img src=https://img.wykw.com/vip/vip_2026.jpg width=300 height=250></a></div>");
					//document.writeln("<div style=\'margin:10px 0px 20px 0px;\'><script  src=\'//a1.51shiti.cn/production/up_oxm/static/qq/resource/qy.js\'></script></div>");		
				}
			}
            break;
			
        case "show_box":
            if (!is_vip) {
				//P_SHOW_RIGHT_DOWN_300x700
				document.writeln("<div id='right_box'><div id='box_float' class='box_div1'><script src='//a1.51shiti.cn/site/wrq/resource/zo/sz_g/q.js'></script></div></div>");
				document.addEventListener('DOMContentLoaded', function() {
					var oDiv = document.getElementById("box_float");
					var originalOffsetTop = oDiv.getBoundingClientRect().top + window.scrollY - 40;

					window.addEventListener('scroll', function() {
						var scrollY = window.scrollY || document.documentElement.scrollTop;
						if (scrollY > originalOffsetTop) {
							oDiv.classList.add("box_div2");
						} else {
							oDiv.classList.remove("box_div2");
						}
					});
				});
			}
            break;
		
    }
}