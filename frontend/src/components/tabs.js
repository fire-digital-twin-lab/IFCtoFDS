(function (ns) {
    ns.components = ns.components || {};

    function Tabs(items, onChange) {
        this.items = items;
        this.onChange = onChange || function () {};
        this.listeners = [];
    }

    Tabs.prototype.mount = function () {
        this.destroy();
        var self = this;
        this.items.forEach(function (item) {
            if (!item.button || !item.panel) return;
            var listener = function () { self.select(item.id); };
            item.button.addEventListener('click', listener);
            self.listeners.push(function () { item.button.removeEventListener('click', listener); });
        });
        return this;
    };

    Tabs.prototype.select = function (id) {
        this.items.forEach(function (item) {
            var active = item.id === id;
            item.button.classList.toggle('active', active);
            item.button.setAttribute('aria-selected', active ? 'true' : 'false');
            item.panel.style.display = active ? item.display : 'none';
        });
        this.onChange(id);
    };

    Tabs.prototype.destroy = function () {
        this.listeners.splice(0).forEach(function (dispose) { dispose(); });
    };

    ns.components.Tabs = Tabs;
})(window.IfcFds);
