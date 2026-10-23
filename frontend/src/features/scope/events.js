(function (ns) {
    ns.app = ns.app || {};
    ns.features = ns.features || {};
    ns.features.scope = ns.features.scope || {};
    ns.features.scope.createScopeEvents = function (dependencies) {
    var life = ns.core.createLifecycle();
    function checkScopedDomainPreflight() { return dependencies.checkScopedDomainPreflight.apply(null, arguments); }
    function updateDomainEstimates() { return dependencies.updateDomainEstimates.apply(null, arguments); }




    var bound = false;
    function bind() {
        if (bound) return;
        bound = true;
        var els = dependencies.getElements();
        // Domain Estimates & Preflight Scoped Domain Warning
        ['xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'].forEach(function (axis) {
            var input = document.getElementById('verified-domain-' + axis);
            if (input) life.listen(input, 'input', updateDomainEstimates);
        });
        if (els.verifiedCellSize) {
            life.listen(els.verifiedCellSize, 'input', updateDomainEstimates);
        }
        if (els.verifiedStoreys) {
            life.listen(els.verifiedStoreys, 'change', checkScopedDomainPreflight);
        }
        if (els.verifiedUseDomain) {
            life.listen(els.verifiedUseDomain, 'change', function () {
                var box = document.getElementById('verified-domain-box');
                if (box) box.style.display = els.verifiedUseDomain.checked ? 'grid' : 'none';
                checkScopedDomainPreflight();
            });
        }
        var useBoundsCheck = document.getElementById('verified-use-bounds');
        var boundsBox = document.getElementById('verified-bounds-box');
        if (useBoundsCheck && boundsBox) {
            life.listen(useBoundsCheck, 'change', function () {
                boundsBox.style.display = useBoundsCheck.checked ? 'grid' : 'none';
            });
        }

        // Reviewed Decisions Upload Summary Preview
        var decisionsInput = document.getElementById('verified-decisions');
        var decisionsChip = document.getElementById('decisions-summary-chip');
        if (decisionsInput && decisionsChip) {
            life.listen(decisionsInput, 'change', async function () {
                if (!decisionsInput.files || !decisionsInput.files.length) {
                    decisionsChip.style.display = 'none';
                    return;
                }
                try {
                    var data = JSON.parse(await decisionsInput.files[0].text());
                    var keys = Object.keys(data);
                    var passive = keys.filter(function (k) { return data[k].action === 'PASSIVE_OBSTACLE'; }).length;
                    var ref = keys.filter(function (k) { return data[k].action === 'REFERENCE_GEOMETRY'; }).length;
                    var excl = keys.filter(function (k) { return data[k].action === 'EXCLUDE'; }).length;
                    decisionsChip.style.display = 'flex';
                    decisionsChip.textContent = '✓ ' + keys.length + ' decisions loaded (' + passive + ' Obstacle, ' + ref + ' Reference, ' + excl + ' Excluded)';
                } catch (e) {
                    decisionsChip.style.display = 'flex';
                    decisionsChip.textContent = '⚠️ Malformed decisions JSON';
                }
            });
        }


    }

    return {bind: bind, destroy: function () { life.destroy(); }};
    };
})(window.IfcFds);
