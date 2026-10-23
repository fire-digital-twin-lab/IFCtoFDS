(function (ns) {
    ns.components = ns.components || {};

    function Modal(root, closeButton, defaultTrigger, resetBody) {
        this.root = root;
        this.closeButton = closeButton;
        this.defaultTrigger = defaultTrigger;
        this.resetBody = resetBody;
        this.trigger = null;
    }

    Modal.prototype.open = function (event) {
        this.trigger = event && event.currentTarget ? event.currentTarget : this.defaultTrigger;
        this.root.hidden = false;
        if (this.resetBody) this.root.querySelector(this.resetBody).scrollTop = 0;
        if (this.closeButton) this.closeButton.focus();
    };

    Modal.prototype.close = function () {
        this.root.hidden = true;
        var trigger = this.trigger || this.defaultTrigger;
        if (trigger) trigger.focus();
    };

    Modal.prototype.destroy = function () {
        this.root.hidden = true;
        this.trigger = null;
    };

    ns.components.Modal = Modal;
})(window.IfcFds);
