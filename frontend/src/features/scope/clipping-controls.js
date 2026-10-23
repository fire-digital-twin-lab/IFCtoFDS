(function (ns) {
    ns.features = ns.features || {};
    ns.features.scope = ns.features.scope || {};
    ns.features.scope.createClippingControls = function (dependencies) {



        function applyClip(id, value) {
            var els = dependencies.getElements(); var viewer = dependencies.getViewer();
            var slider = els.clipSliders[id];
            var input = els.clipInputs[id];
            if (slider) slider.value = String(value);
            if (input) input.value = Number(value).toFixed(2);
            var axisChar = id.charAt(0);
            var side = id.slice(1);
            viewer.setClipPlane(axisChar, side, Number(value));
        }

        function clampClip(id, raw) {
            var els = dependencies.getElements();
            var slider = els.clipSliders[id];
            if (!slider) return raw;
            var v = Number(raw);
            if (!isFinite(v)) return Number(slider.value);
            return Math.max(Number(slider.min), Math.min(Number(slider.max), v));
        }

        function bindClipSlider(id) {
            var els = dependencies.getElements();
            var slider = els.clipSliders[id];
            var input = els.clipInputs[id];
            if (!slider) return;
            slider.addEventListener('input', function () { applyClip(id, slider.value); });
            if (input) {
                input.addEventListener('change', function () { applyClip(id, clampClip(id, input.value)); });
                input.addEventListener('keydown', function (event) {
                    if (event.key === 'Enter') input.blur();
                });
            }
        }

        function bindClipSteppers() {
            var els = dependencies.getElements();
            Array.prototype.forEach.call(document.querySelectorAll('.clip-step'), function (btn) {
                btn.addEventListener('click', function () {
                    var id = String(btn.getAttribute('data-target') || '').replace(/^clip-/, '');
                    var dir = Number(btn.getAttribute('data-dir')) || 0;
                    var slider = els.clipSliders[id];
                    if (!slider) return;
                    var step = Number(slider.step) || 0.1;
                    var current = Number(slider.value);
                    applyClip(id, clampClip(id, current + dir * step));
                });
            });
        }

        function setupClippingForBounds(bounds) {
            var els = dependencies.getElements(); var viewer = dependencies.getViewer();
            if (!els.clipPanel) return;
            if (!bounds) { els.clipPanel.hidden = true; return; }
            els.clipPanel.hidden = false;
            var pairs = [['xmin', 'xmax', bounds.xmin, bounds.xmax], ['ymin', 'ymax', bounds.ymin, bounds.ymax], ['zmin', 'zmax', bounds.zmin, bounds.zmax]];
            pairs.forEach(function (p) {
                var lo = p[2], hi = p[3];
                var span = Math.max(hi - lo, 0.001);
                // Step granularity: round to a sensible nudge (cm-scale on a metre-scale model)
                // so the ▲/▼ buttons feel like 0.01–0.1 m per click rather than fractional µm.
                var step = Math.max(span / 200, 0.01);
                [[p[0], lo], [p[1], hi]].forEach(function (pair) {
                    var id = pair[0], value = pair[1];
                    var slider = els.clipSliders[id];
                    var input = els.clipInputs[id];
                    if (slider) { slider.min = String(lo); slider.max = String(hi); slider.step = String(step); slider.value = String(value); }
                    if (input) input.value = Number(value).toFixed(2);
                });
            });
            viewer.setClipBoundsNative(bounds);
        }

        function updateDomainEstimates() {
            var els = dependencies.getElements();
            if (ns.ui && ns.ui.domainPanel) {
                ns.ui.domainPanel.updateDomainEstimates(els);
            }
        }

        function checkScopedDomainPreflight() {
            var els = dependencies.getElements();
            if (ns.ui && ns.ui.domainPanel) {
                ns.ui.domainPanel.checkScopedDomainPreflight(els);
            }
        }

        return {
            applyClip: applyClip,
            clampClip: clampClip,
            bindClipSlider: bindClipSlider,
            bindClipSteppers: bindClipSteppers,
            setupClippingForBounds: setupClippingForBounds,
            updateDomainEstimates: updateDomainEstimates,
            checkScopedDomainPreflight: checkScopedDomainPreflight
        };
    };
})(window.IfcFds);
