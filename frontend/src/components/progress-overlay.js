(function (ns) {
    ns.components = ns.components || {};

    function ProgressOverlay(elements) {
        this.elements = elements;
    }

    ProgressOverlay.prototype.show = function (title, stage) {
        var els = this.elements;
        if (!els.ifcLoading) return;
        els.ifcLoadingTitle.textContent = title || 'Loading IFC.';
        els.ifcLoadingStage.textContent = stage || '';
        els.ifcLoadingPercent.textContent = '';
        els.ifcLoadingFill.classList.add('is-indeterminate');
        els.ifcLoadingFill.style.width = '';
        els.ifcLoading.hidden = false;
    };

    ProgressOverlay.prototype.update = function (fraction, stage) {
        var els = this.elements;
        if (!els.ifcLoading || els.ifcLoading.hidden) return;
        if (stage !== undefined) els.ifcLoadingStage.textContent = stage;
        var f = Math.max(0, Math.min(1, fraction || 0));
        els.ifcLoadingFill.classList.remove('is-indeterminate');
        els.ifcLoadingFill.style.width = (f * 100).toFixed(1) + '%';
        els.ifcLoadingPercent.textContent = Math.round(f * 100) + '%';
    };

    ProgressOverlay.prototype.hide = function () {
        var els = this.elements;
        if (!els.ifcLoading) return;
        els.ifcLoading.hidden = true;
        els.ifcLoadingFill.classList.add('is-indeterminate');
        els.ifcLoadingFill.style.width = '';
    };

    ns.components.ProgressOverlay = ProgressOverlay;
})(window.IfcFds);
