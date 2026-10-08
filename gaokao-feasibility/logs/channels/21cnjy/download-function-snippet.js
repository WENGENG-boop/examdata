function down_load_resource(e, paySuit, assetId) {
        var isLogin = 0; //是否登录
        var activity_bind_book = 0;
        if (!isLogin) {

            window.location = 'https://passport.21cnjy.com/login?jump_url=https://book.21cnjy.com/store/311667.shtml';
            return false;
        }

        var assetIds = assetId || []
        var bookId = 311667;
        if (!assetId) {
            $('.book-detail--chapter-list .active').each(function() {
                assetIds.push($(this).attr('data-itemids'));
            });
            if (!assetIds.length) {
                //先显示错误信息然后1s后隐藏
                $(".pop--wrapper").show().delay(1000).fadeOut();
                return $.ajax();
            }
        }
        // 多份资料需要弹出明细表
        if(assetIds.length > 1) {
            var remainCoin = 0;
            var mx = new MyLib.DownloadDataT({propsData:{assetIds:assetIds,bookId:bookId,remainCoin:remainCoin,is12Activity: activity_bind_book,specialSetting: specialSetting}}).$mount();
            $(document).on("click",".confirm-btn", function() {
                // 防止多次点击
                if(isClick) {
                    isClick = false
                    popMount(paySuit, assetIds,mx).then(function() {
                        isClick = true
                    })
                }
                
            })
            
            return mx.showModal();;
        }