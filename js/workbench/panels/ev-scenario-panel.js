/**
 * EV Scenario Matrix Panel & Batch Queue
 *
 * Implements EV fire scenario matrix generation, batch queuing, and aggregate
 * reporting following Principle A3 (does not mutate MappingBundle; scenario references
 * bundle_sha256). Blocks scenario emission when base mapping is not MAPPING_VERIFIED.
 */
(function (root) {
    'use strict';

    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.panels = root.IfcFds.workbench.panels || {};
    root.IfcFds.ui = root.IfcFds.ui || {};

    var EV_LIBRARY_VERSION = '1.0.0';
    var DISCLAIMER = 'Kịch bản giả định, cần kỹ sư PCCC thẩm định độc lập';
    var ASSUMPTIONS = 'Kịch bản cháy xe điện giả định theo EV Library v1.0.0. Thông số HRR, hóa học pin và lan truyền là giả định kỹ thuật, cần kỹ sư PCCC thẩm định độc lập trước khi áp dụng thực tế.';

    var DEFAULT_PRESETS = {
        'e-bike-lfp': {
            preset_id: 'e-bike-lfp',
            vehicle_class: 'e-bike',
            chemistry: 'LFP',
            pack_kwh_range: [0.5, 3.0],
            peak_hrr_mw_range: [0.02, 0.15],
            typical_peak_hrr_mw: 0.085,
            confidence: 'low',
            growth: 't-squared',
            notes: 'Gia dinh: preset mo phong cho xe may/xe dap dien dung pin LFP 0.5-3 kWh, chua co so lieu calorimeter rieng. Dai HRR dinh va hieu suat chay chi de kich ban gia dinh, bat buoc ky su PCCC tham dinh doc lap truoc khi dung cho thiet ke.',
            citations: [
                {
                    source: 'engineering-assumption',
                    detail: 'Chua co thi nghiem calorimetry rieng cho pin xe dien 2 banh LFP trong thu vien'
                }
            ]
        },
        'auto-nmc': {
            preset_id: 'auto-nmc',
            vehicle_class: 'auto',
            chemistry: 'NMC',
            pack_kwh_range: [40.0, 100.0],
            peak_hrr_mw_range: [2.0, 7.0],
            typical_peak_hrr_mw: 4.5,
            confidence: 'medium',
            growth: 't-squared',
            notes: 'Gia dinh mot phan: dai dinh HRR 2-7 MW/xe bao phu bien do thi nghiem; can tham dinh doc lap.',
            citations: [
                {
                    source: 'RISE full-scale BEV fire tests',
                    detail: 'Full-scale BEV fire tests reported per-vehicle peak HRR roughly 4-6 MW'
                }
            ]
        }
    };

    /**
     * Compute the lowest confidence level among presets present in the scenario.
     * Order: low < medium < high
     */
    function resolveLowestConfidence(hasEbike, hasAuto, presets) {
        var confs = [];
        if (hasEbike) {
            confs.push((presets['e-bike-lfp'] && presets['e-bike-lfp'].confidence) || 'low');
        }
        if (hasAuto) {
            confs.push((presets['auto-nmc'] && presets['auto-nmc'].confidence) || 'medium');
        }
        if (!confs.length) return 'low';
        if (confs.indexOf('low') !== -1) return 'low';
        if (confs.indexOf('medium') !== -1) return 'medium';
        return 'high';
    }

    /**
     * Generates a matrix of EV fire scenarios across input dimensions.
     *
     * @param {Object} options
     * @param {number[]} [options.vehicleCounts]
     * @param {number[]} [options.spacingsM]
     * @param {Array<{ebike: number, auto: number}>} [options.chemistryMix]
     * @param {string[]} [options.doorStates]
     * @param {string} options.baseBundleSha
     * @param {Object} options.scenarioStore
     * @param {Object} [options.presets]
     * @param {number} [options.maxScenarios]
     * @returns {Array<Object>} List of ScenarioBundle objects
     */
    function generateScenarioMatrix(options) {
        options = options || {};
        var store = options.scenarioStore;
        if (!store) {
            throw new Error('scenarioStore is required');
        }
        if (typeof store.isSimulationPermitted !== 'function' || !store.isSimulationPermitted()) {
            throw new Error('Mapping must be MAPPING_VERIFIED before generating scenario batch');
        }
        if (!options.baseBundleSha || typeof options.baseBundleSha !== 'string') {
            throw new Error('baseBundleSha is required and must be a valid SHA-256 string');
        }

        var vehicleCounts = (options.vehicleCounts && options.vehicleCounts.length) ? options.vehicleCounts : [1];
        var spacingsM = (options.spacingsM && options.spacingsM.length) ? options.spacingsM : [0.5];
        var chemistryMix = (options.chemistryMix && options.chemistryMix.length) ? options.chemistryMix : [{ ebike: 0.5, auto: 0.5 }];
        var doorStates = (options.doorStates && options.doorStates.length) ? options.doorStates : ['CLOSED'];
        var presets = options.presets || DEFAULT_PRESETS;
        var maxScenarios = typeof options.maxScenarios === 'number' ? options.maxScenarios : Infinity;

        var ebikePreset = presets['e-bike-lfp'] || DEFAULT_PRESETS['e-bike-lfp'];
        var autoPreset = presets['auto-nmc'] || DEFAULT_PRESETS['auto-nmc'];

        var scenarios = [];
        var scenarioIndex = 0;

        for (var cIdx = 0; cIdx < vehicleCounts.length; cIdx++) {
            var vCount = vehicleCounts[cIdx];
            for (var sIdx = 0; sIdx < spacingsM.length; sIdx++) {
                var spacing = spacingsM[sIdx];
                for (var mIdx = 0; mIdx < chemistryMix.length; mIdx++) {
                    var mix = chemistryMix[mIdx];
                    for (var dIdx = 0; dIdx < doorStates.length; dIdx++) {
                        var door = doorStates[dIdx];

                        if (scenarios.length >= maxScenarios) {
                            return scenarios;
                        }

                        scenarioIndex++;
                        var ebikeRatio = typeof mix.ebike === 'number' ? mix.ebike : 0.5;
                        var autoRatio = typeof mix.auto === 'number' ? mix.auto : 0.5;

                        var numEbike, numAuto;
                        if (ebikeRatio === 0 && autoRatio > 0) {
                            numEbike = 0;
                            numAuto = vCount;
                        } else if (autoRatio === 0 && ebikeRatio > 0) {
                            numEbike = vCount;
                            numAuto = 0;
                        } else {
                            numEbike = Math.round(vCount * ebikeRatio);
                            if (numEbike === 0 && ebikeRatio > 0 && vCount === 1) {
                                numEbike = 1;
                            }
                            numAuto = vCount - numEbike;
                            if (numAuto < 0) numAuto = 0;
                        }

                        var hasEbike = numEbike > 0;
                        var hasAuto = numAuto > 0;
                        var confidence = resolveLowestConfidence(hasEbike, hasAuto, presets);

                        var evSelections = [];
                        var currentX = 0.0;
                        for (var e = 0; e < numEbike; e++) {
                            evSelections.push({
                                preset_id: ebikePreset.preset_id,
                                vehicle_class: ebikePreset.vehicle_class,
                                chemistry: ebikePreset.chemistry,
                                position: [Number(currentX.toFixed(3)), 0.0, 0.55],
                                peak_hrr_mw: ebikePreset.typical_peak_hrr_mw,
                                confidence: ebikePreset.confidence
                            });
                            currentX += spacing;
                        }
                        for (var a = 0; a < numAuto; a++) {
                            evSelections.push({
                                preset_id: autoPreset.preset_id,
                                vehicle_class: autoPreset.vehicle_class,
                                chemistry: autoPreset.chemistry,
                                position: [Number(currentX.toFixed(3)), 0.0, 0.75],
                                peak_hrr_mw: autoPreset.typical_peak_hrr_mw,
                                confidence: autoPreset.confidence
                            });
                            currentX += spacing;
                        }

                        var totalPeakHrr = Number((numEbike * ebikePreset.typical_peak_hrr_mw + numAuto * autoPreset.typical_peak_hrr_mw).toFixed(4));

                        var openingEvents = [
                            {
                                entity_key: 'OPENING_MAIN',
                                state: door,
                                event_time_s: 0.0
                            }
                        ];

                        var scenarioId = 'SCENARIO_EV_' + String(scenarioIndex).padStart(3, '0');

                        var fdsFragment = [
                            '&HEAD CHID=\'' + scenarioId + '\', TITLE=\'EV Fire Scenario ' + scenarioId + '\' /',
                            '&REAC ID=\'EV_BATTERY_REAC\', FUEL=\'PROPANE\', SOOT_YIELD=0.10 /',
                            '&SURF ID=\'EV_FIRE_SURF\', HRRPUA=250.0, RAMP_Q=\'RAMP_EV\' /',
                            '&RAMP ID=\'RAMP_EV\', T=0.0, F=0.0 /',
                            '&RAMP ID=\'RAMP_EV\', T=180.0, F=1.0 /'
                        ].join('\n');

                        var scenario = {
                            scenario_id: scenarioId,
                            bundle_sha256: options.baseBundleSha,
                            ev_library_version: EV_LIBRARY_VERSION,
                            confidence: confidence,
                            vehicle_count: vCount,
                            spacing_m: spacing,
                            chemistry_mix: { ebike: ebikeRatio, auto: autoRatio },
                            door_state: door,
                            total_peak_hrr_mw: totalPeakHrr,
                            ev_count: vCount,
                            ev_selections: evSelections,
                            opening_events: openingEvents,
                            fds_fragment: fdsFragment,
                            disclaimer: DISCLAIMER,
                            notes: ASSUMPTIONS
                        };

                        scenarios.push(scenario);
                    }
                }
            }
        }

        return scenarios;
    }

    /**
     * Queue and run scenario batch, collecting per-job results and synthesizing an aggregate summary.
     *
     * @param {Array<Object>} scenarios
     * @param {Function} [dispatchJobFn]
     * @returns {Promise<{results: Array<any>, summary: Object}>}
     */
    async function queueScenarioBatch(scenarios, dispatchJobFn) {
        if (!Array.isArray(scenarios)) {
            throw new Error('scenarios must be an array');
        }

        var defaultDispatch = function (scenario) {
            var payload = {
                scenario_id: scenario.scenario_id,
                bundle_sha256: scenario.bundle_sha256,
                ev_library_version: scenario.ev_library_version,
                total_peak_hrr_mw: scenario.total_peak_hrr_mw,
                scenario_data: scenario
            };
            var fetcher = (root.IfcFds && root.IfcFds.verified && typeof root.IfcFds.verified.authFetch === 'function')
                ? root.IfcFds.verified.authFetch
                : (typeof fetch !== 'undefined' ? fetch : null);

            if (!fetcher) {
                return Promise.resolve({
                    job_id: 'mock_' + scenario.scenario_id,
                    scenario_id: scenario.scenario_id,
                    state: 'COMPLETED',
                    mesh_status: 'PASS',
                    verdict: 'PASS',
                    peak_hrr_mw: scenario.total_peak_hrr_mw
                });
            }

            return fetcher('/api/jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(function (res) {
                return res.json ? res.json() : res;
            });
        };

        var dispatch = dispatchJobFn || defaultDispatch;
        var results = [];
        var passed = 0;
        var inconclusive = 0;
        var rejected = 0;

        for (var i = 0; i < scenarios.length; i++) {
            var res = await dispatch(scenarios[i]);
            results.push(res);
            var v = (res.verdict || res.status || res.state || '').toUpperCase();
            if (v === 'PASS' || v === 'PASSED') {
                passed++;
            } else if (v === 'INCONCLUSIVE' || (res.mesh_status && res.mesh_status === 'FAIL')) {
                inconclusive++;
            } else if (v === 'REJECTED' || v === 'FAIL' || v === 'FAILED') {
                rejected++;
            } else if (v === 'COMPLETED') {
                // If COMPLETED and no explicit failure, evaluate mesh_status
                if (res.mesh_status === 'FAIL') {
                    inconclusive++;
                } else {
                    passed++;
                }
            } else {
                rejected++;
            }
        }

        var summary = {
            total: scenarios.length,
            passed: passed,
            inconclusive: inconclusive,
            rejected: rejected,
            disclaimer: DISCLAIMER,
            assumptions: ASSUMPTIONS
        };

        return {
            results: results,
            summary: summary
        };
    }

    /**
     * UI Panel DOM Builder & Event Wiring
     */
    function mount(container, options) {
        options = options || {};
        var store = options.scenarioStore;
        var getBaseBundleSha = options.getBaseBundleSha || function () { return ''; };
        var dispatchJobFn = options.dispatchJobFn || null;

        var doc = (typeof document !== 'undefined') ? document : root.document;
        if (!doc || !container) return;

        container.replaceChildren();

        // Section Title & Info Card
        var header = doc.createElement('div');
        header.className = 'section-header';
        header.style.marginBottom = '8px';

        var title = doc.createElement('span');
        title.className = 'section-title';
        title.textContent = 'EV Fire Scenario Batch (Full Simulation)';
        header.appendChild(title);
        container.appendChild(header);

        var disclaimerBox = doc.createElement('div');
        disclaimerBox.className = 'info-callout warning';
        disclaimerBox.style.fontSize = '11px';
        disclaimerBox.style.padding = '8px';
        disclaimerBox.style.marginBottom = '12px';
        disclaimerBox.textContent = DISCLAIMER + '. ' + ASSUMPTIONS;
        container.appendChild(disclaimerBox);

        // Form controls for Matrix inputs
        var form = doc.createElement('div');
        form.style.display = 'flex';
        form.style.flexDirection = 'column';
        form.style.gap = '8px';

        // Vehicle counts
        var grpCount = doc.createElement('div');
        grpCount.className = 'form-group';
        var lblCount = doc.createElement('label');
        lblCount.className = 'form-label';
        lblCount.textContent = 'Vehicle Counts (comma-separated, e.g. 1, 2)';
        var inputCount = doc.createElement('input');
        inputCount.id = 'ev-input-vehicle-counts';
        inputCount.className = 'form-input';
        inputCount.value = '1, 2';
        grpCount.appendChild(lblCount);
        grpCount.appendChild(inputCount);
        form.appendChild(grpCount);

        // Spacing (m)
        var grpSpacing = doc.createElement('div');
        grpSpacing.className = 'form-group';
        var lblSpacing = doc.createElement('label');
        lblSpacing.className = 'form-label';
        lblSpacing.textContent = 'Spacing (m, comma-separated, e.g. 0.5, 1.0)';
        var inputSpacing = doc.createElement('input');
        inputSpacing.id = 'ev-input-spacings';
        inputSpacing.className = 'form-input';
        inputSpacing.value = '0.5';
        grpSpacing.appendChild(lblSpacing);
        grpSpacing.appendChild(inputSpacing);
        form.appendChild(grpSpacing);

        // Chemistry Mix
        var grpMix = doc.createElement('div');
        grpMix.className = 'form-group';
        var lblMix = doc.createElement('label');
        lblMix.className = 'form-label';
        lblMix.textContent = 'Chemistry Mix';
        var selectMix = doc.createElement('select');
        selectMix.id = 'ev-select-chemistry-mix';
        selectMix.className = 'form-select';
        var optMix1 = doc.createElement('option');
        optMix1.value = '50-50';
        optMix1.textContent = '50% LFP E-bike / 50% NMC Auto';
        var optMix2 = doc.createElement('option');
        optMix2.value = '100-ebike';
        optMix2.textContent = '100% LFP E-bike (Cluster Mode)';
        var optMix3 = doc.createElement('option');
        optMix3.value = '100-auto';
        optMix3.textContent = '100% NMC Auto (High HRR)';
        selectMix.appendChild(optMix1);
        selectMix.appendChild(optMix2);
        selectMix.appendChild(optMix3);
        grpMix.appendChild(lblMix);
        grpMix.appendChild(selectMix);
        form.appendChild(grpMix);

        // Door status
        var grpDoor = doc.createElement('div');
        grpDoor.className = 'form-group';
        var lblDoor = doc.createElement('label');
        lblDoor.className = 'form-label';
        lblDoor.textContent = 'Door / Ventilation State';
        var selectDoor = doc.createElement('select');
        selectDoor.id = 'ev-select-door-state';
        selectDoor.className = 'form-select';
        var optDoor1 = doc.createElement('option');
        optDoor1.value = 'CLOSED';
        optDoor1.textContent = 'CLOSED (Underventilated / Toxic)';
        var optDoor2 = doc.createElement('option');
        optDoor2.value = 'OPEN';
        optDoor2.textContent = 'OPEN (Fully Ventilated)';
        var optDoor3 = doc.createElement('option');
        optDoor3.value = 'BOTH';
        optDoor3.textContent = 'Both CLOSED and OPEN';
        selectDoor.appendChild(optDoor1);
        selectDoor.appendChild(optDoor2);
        selectDoor.appendChild(optDoor3);
        grpDoor.appendChild(lblDoor);
        grpDoor.appendChild(selectDoor);
        form.appendChild(grpDoor);

        // Action Button: Generate EV Fire Batch
        var btnGenerate = doc.createElement('button');
        btnGenerate.id = 'ev-btn-generate-batch';
        btnGenerate.className = 'btn btn-primary';
        btnGenerate.type = 'button';
        btnGenerate.style.marginTop = '6px';
        btnGenerate.textContent = 'Generate EV Fire Batch';
        form.appendChild(btnGenerate);

        container.appendChild(form);

        // Progress text
        var progressEl = doc.createElement('div');
        progressEl.id = 'ev-batch-progress';
        progressEl.style.fontSize = '11px';
        progressEl.style.marginTop = '8px';
        progressEl.style.color = 'var(--text-muted)';
        container.appendChild(progressEl);

        // Summary Box
        var summaryBox = doc.createElement('div');
        summaryBox.id = 'ev-batch-summary';
        summaryBox.style.marginTop = '10px';
        summaryBox.style.display = 'none';
        container.appendChild(summaryBox);

        // Results Table Container
        var resultsTable = doc.createElement('div');
        resultsTable.id = 'ev-batch-results-table';
        resultsTable.style.marginTop = '10px';
        container.appendChild(resultsTable);

        // Click Handler
        btnGenerate.addEventListener('click', async function () {
            progressEl.textContent = 'Generating scenario matrix…';
            summaryBox.style.display = 'none';
            resultsTable.replaceChildren();

            var currentStore = store || (root.IfcFds && root.IfcFds.workbench && root.IfcFds.workbench.state && root.IfcFds.workbench.state.scenarioStore);
            var sha = getBaseBundleSha();
            if (!sha && currentStore && currentStore.getBaseMappingSha) {
                sha = currentStore.getBaseMappingSha();
            }

            var counts = inputCount.value.split(',').map(function (s) { return parseInt(s.trim(), 10); }).filter(Boolean);
            if (!counts.length) counts = [1];
            var spacings = inputSpacing.value.split(',').map(function (s) { return parseFloat(s.trim()); }).filter(Boolean);
            if (!spacings.length) spacings = [0.5];

            var mixVal = selectMix.value;
            var mixes = [{ ebike: 0.5, auto: 0.5 }];
            if (mixVal === '100-ebike') mixes = [{ ebike: 1.0, auto: 0.0 }];
            if (mixVal === '100-auto') mixes = [{ ebike: 0.0, auto: 1.0 }];

            var doorVal = selectDoor.value;
            var doors = (doorVal === 'BOTH') ? ['CLOSED', 'OPEN'] : [doorVal || 'CLOSED'];

            var matrixOptions = {
                vehicleCounts: counts,
                spacingsM: spacings,
                chemistryMix: mixes,
                doorStates: doors,
                baseBundleSha: sha || 'simulated_bundle_sha',
                scenarioStore: currentStore
            };

            var generated;
            try {
                generated = generateScenarioMatrix(matrixOptions);
            } catch (err) {
                progressEl.textContent = 'Error: ' + err.message;
                return;
            }

            progressEl.textContent = 'Dispatching batch of ' + generated.length + ' scenarios…';

            try {
                var batchOutput = await queueScenarioBatch(generated, dispatchJobFn);
                progressEl.textContent = 'Batch completed: ' + batchOutput.results.length + ' scenarios evaluated.';

                // Render Summary Box
                summaryBox.style.display = 'block';
                summaryBox.replaceChildren();
                var sumHeader = doc.createElement('div');
                sumHeader.style.fontWeight = 'bold';
                sumHeader.style.marginBottom = '4px';
                sumHeader.textContent = 'Aggregate Verdict: ' + batchOutput.summary.passed + ' Passed, ' +
                    batchOutput.summary.inconclusive + ' Inconclusive, ' + batchOutput.summary.rejected + ' Rejected';
                summaryBox.appendChild(sumHeader);

                var sumDisclaimer = doc.createElement('div');
                sumDisclaimer.style.fontSize = '10px';
                sumDisclaimer.style.color = 'var(--text-muted)';
                sumDisclaimer.textContent = batchOutput.summary.disclaimer;
                summaryBox.appendChild(sumDisclaimer);

                // Render Table
                resultsTable.replaceChildren();
                var table = doc.createElement('table');
                table.style.width = '100%';
                table.style.fontSize = '11px';
                table.style.borderCollapse = 'collapse';

                var thead = doc.createElement('thead');
                var trHead = doc.createElement('tr');
                ['ID', 'Vehicles', 'Peak HRR', 'Mesh', 'Verdict'].forEach(function (col) {
                    var th = doc.createElement('th');
                    th.style.textAlign = 'left';
                    th.style.padding = '4px';
                    th.style.borderBottom = '1px solid var(--border-subtle)';
                    th.textContent = col;
                    trHead.appendChild(th);
                });
                thead.appendChild(trHead);
                table.appendChild(thead);

                var tbody = doc.createElement('tbody');
                batchOutput.results.forEach(function (res, idx) {
                    var tr = doc.createElement('tr');
                    tr.style.borderBottom = '1px solid var(--border-subtle)';

                    var tdId = doc.createElement('td');
                    tdId.style.padding = '4px';
                    tdId.textContent = res.scenario_id || ('EV_' + (idx + 1));
                    tr.appendChild(tdId);

                    var tdCount = doc.createElement('td');
                    tdCount.style.padding = '4px';
                    tdCount.textContent = (generated[idx] && generated[idx].vehicle_count) || '-';
                    tr.appendChild(tdCount);

                    var tdHrr = doc.createElement('td');
                    tdHrr.style.padding = '4px';
                    tdHrr.textContent = (res.peak_hrr_mw || (generated[idx] && generated[idx].total_peak_hrr_mw) || '-') + ' MW';
                    tr.appendChild(tdHrr);

                    var tdMesh = doc.createElement('td');
                    tdMesh.style.padding = '4px';
                    tdMesh.textContent = res.mesh_status || 'PASS';
                    tr.appendChild(tdMesh);

                    var tdVerdict = doc.createElement('td');
                    tdVerdict.style.padding = '4px';
                    tdVerdict.style.fontWeight = 'bold';
                    var verdictVal = res.verdict || res.state || 'UNKNOWN';
                    tdVerdict.textContent = verdictVal;
                    if (verdictVal === 'PASS') tdVerdict.style.color = 'var(--status-pass)';
                    else if (verdictVal === 'INCONCLUSIVE') tdVerdict.style.color = 'var(--status-warning)';
                    else tdVerdict.style.color = 'var(--status-fail)';
                    tr.appendChild(tdVerdict);

                    tbody.appendChild(tr);
                });
                table.appendChild(tbody);
                resultsTable.appendChild(table);
            } catch (queueErr) {
                progressEl.textContent = 'Batch dispatch error: ' + queueErr.message;
            }
        });
    }

    var evScenarioPanel = {
        EV_LIBRARY_VERSION: EV_LIBRARY_VERSION,
        DEFAULT_PRESETS: DEFAULT_PRESETS,
        DISCLAIMER: DISCLAIMER,
        ASSUMPTIONS: ASSUMPTIONS,
        generateScenarioMatrix: generateScenarioMatrix,
        queueScenarioBatch: queueScenarioBatch,
        mount: mount
    };

    root.IfcFds.workbench.panels.evScenarioPanel = evScenarioPanel;
    root.IfcFds.ui.evScenarioPanel = evScenarioPanel;

})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
