/**
 * Simulation Domain Panel for IFCtoFDS Research Workbench.
 * Handles domain bounds, grid cell calculations, memory budget heuristics,
 * and scoped storey preflight warnings.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.ui = root.IfcFds.ui || {};

    function updateDomainEstimates(els) {
        var xminInput = document.getElementById('verified-domain-xmin');
        var xmaxInput = document.getElementById('verified-domain-xmax');
        var yminInput = document.getElementById('verified-domain-ymin');
        var ymaxInput = document.getElementById('verified-domain-ymax');
        var zminInput = document.getElementById('verified-domain-zmin');
        var zmaxInput = document.getElementById('verified-domain-zmax');
        var cellInput = document.getElementById('verified-cell-size') || (els && els.meshCellSize);

        var xmin = Number(xminInput ? xminInput.value : 0) || 0;
        var xmax = Number(xmaxInput ? xmaxInput.value : 10) || 10;
        var ymin = Number(yminInput ? yminInput.value : 0) || 0;
        var ymax = Number(ymaxInput ? ymaxInput.value : 10) || 10;
        var zmin = Number(zminInput ? zminInput.value : 0) || 0;
        var zmax = Number(zmaxInput ? zmaxInput.value : 3) || 3;
        var cellSize = Math.max(0.01, Number(cellInput ? cellInput.value : 0.20) || 0.20);

        var dx = Math.max(0.01, Math.abs(xmax - xmin));
        var dy = Math.max(0.01, Math.abs(ymax - ymin));
        var dz = Math.max(0.01, Math.abs(zmax - zmin));

        var cellsX = Math.ceil(dx / cellSize);
        var cellsY = Math.ceil(dy / cellSize);
        var cellsZ = Math.ceil(dz / cellSize);
        var totalCells = cellsX * cellsY * cellsZ;

        var dimText = (els && els.domainDimensionsText) || document.getElementById('domain-dimensions-text');
        if (dimText) {
            dimText.textContent = dx.toFixed(1) + ' × ' + dy.toFixed(1) + ' × ' + dz.toFixed(1) + ' m';
        }

        var estCells = (els && els.domainEstCells) || document.getElementById('domain-est-cells');
        if (estCells) {
            estCells.textContent = totalCells.toLocaleString() + ' cells';
        }

        var estBudget = (els && els.domainEstBudget) || document.getElementById('domain-est-budget');
        if (estBudget) {
            if (totalCells <= 10000000) {
                estBudget.className = 'domain-budget-chip reasonable';
                estBudget.textContent = '● OK';
            } else if (totalCells <= 50000000) {
                estBudget.className = 'domain-budget-chip heavy';
                estBudget.textContent = '▲ Heavy';
            } else {
                estBudget.className = 'domain-budget-chip heavy';
                estBudget.textContent = '⚠️ Critical (>50M)';
            }
        }
    }

    function checkScopedDomainPreflight(els) {
        var storeys = (els && els.verifiedStoreys) || document.getElementById('verified-storeys');
        var useDomain = (els && els.verifiedUseDomain) || document.getElementById('verified-use-domain');
        var warning = (els && els.verifiedDomainWarning) || document.getElementById('verified-domain-warning');
        if (!storeys || !useDomain || !warning) return;
        var hasSelectedStoreys = Array.prototype.some.call(storeys.options, function (o) { return o.selected; });
        var hasDomain = useDomain.checked;
        warning.style.display = (hasSelectedStoreys && !hasDomain) ? 'flex' : 'none';
    }

    function init(els) {
        ['xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'].forEach(function (axis) {
            var input = document.getElementById('verified-domain-' + axis);
            if (input) {
                input.addEventListener('input', function () { updateDomainEstimates(els); });
            }
        });

        var cellSizeInput = document.getElementById('verified-cell-size');
        if (cellSizeInput) {
            cellSizeInput.addEventListener('input', function () { updateDomainEstimates(els); });
        }

        var storeysEl = (els && els.verifiedStoreys) || document.getElementById('verified-storeys');
        if (storeysEl) {
            storeysEl.addEventListener('change', function () { checkScopedDomainPreflight(els); });
        }

        var useDomainEl = (els && els.verifiedUseDomain) || document.getElementById('verified-use-domain');
        if (useDomainEl) {
            useDomainEl.addEventListener('change', function () { checkScopedDomainPreflight(els); });
        }

        updateDomainEstimates(els);
        checkScopedDomainPreflight(els);
    }

    root.IfcFds.ui.domainPanel = {
        init: init,
        updateDomainEstimates: updateDomainEstimates,
        checkScopedDomainPreflight: checkScopedDomainPreflight
    };
})(window);
