(function (ns) {
    function start() {
        if (ns.app.instance) ns.app.instance.destroy();
        ns.app.instance = ns.app.createApplication();
        ns.app.instance.mount();
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
    else start();
})(window.IfcFds);
