(function (ns) {
    'use strict';
    var jobId = null, stopped = false, fallback = null, generation = 0;
    function cancelled() { var error = new Error('Conversion cancelled'); error.name = 'AbortError'; return error; }
    function get(id) { return document.getElementById('verified-' + id); }
    function files() { return Array.prototype.slice.call(get('sources').files || []); }
    function selectedFiles() { return files().length ? files() : (fallback ? [fallback] : []); }
    function progress(text) { get('progress').textContent = text; }
    function response(res) {
        return res.json().then(function (data) {
            if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
            return data;
        });
    }
    function readInventory() {
        var data = new FormData();
        selectedFiles().forEach(function (file) { data.append('files', file); });
        progress('Reading inventory…');
        return fetch('/api/inventory', {method: 'POST', body: data}).then(response).then(function (inventory) {
            get('storeys').replaceChildren();
            inventory.storey_references.forEach(function (storey) {
                var option = document.createElement('option');
                option.value = storey.storey_id;
                option.textContent = storey.name + ' [' + storey.source_id.slice(0, 8) + ' / ' + (storey.building_id || 'unassigned').split(':').pop() + ' / #' + storey.storey_id.split(':').pop() + ']';
                get('storeys').appendChild(option);
            });
            progress(inventory.total_elements + ' entities in ' + inventory.sources.length + ' sources');
            get('research-notice').textContent = (inventory.research.known_cases || []).map(function (c) { return c.name + ' [' + c.source_match + '] — research parity NOT RUN. Choose research profile and reference to compare.'; }).join(' ');
        }).catch(function (err) { progress(err.message); });
    }
    function transformInputs() {
        get('transforms').replaceChildren();
        if (files().length < 2) return;
        files().forEach(function (file, index) {
            var fieldset = document.createElement('fieldset');
            var legend = document.createElement('legend'); legend.textContent = file.name; fieldset.appendChild(legend);
            ['X (m)', 'Y (m)', 'Z (m)', 'Rotation Z (degrees)'].forEach(function (name, axis) {
                var label = document.createElement('label'); label.textContent = name;
                var input = document.createElement('input'); input.type = 'number'; input.step = 'any'; input.value = '0';
                input.id = 'verified-transform-' + index + '-' + axis;
                label.appendChild(input); fieldset.appendChild(label);
            });
            get('transforms').appendChild(fieldset);
        });
    }
    ns.verified = {
        hasFiles: function () { return files().length > 0; },
        setFallback: function (file) { fallback = file; },
        cancel: function () {
            stopped = true; generation++;
            var active = jobId; jobId = null; get('cancel').disabled = true;
            return active ? fetch('/api/jobs/' + active, {method: 'DELETE'}).then(response) : Promise.resolve();
        },
        init: function () {
            fetch('/api/reference-cases').then(response).then(function (data) {
                data.cases.forEach(function (entry) {
                    var id = entry.id;
                    var option = document.createElement('option'); option.value = id; option.textContent = entry.name + ' (' + entry.approval_status + ')';
                    get('reference-case').appendChild(option);
                });
            }).catch(function () {});
            get('sources').addEventListener('change', function () {
                ns.verified.cancel().catch(function (err) { progress(err.message); });
                transformInputs(); get('storeys').replaceChildren();
                document.getElementById('convert-verified').disabled = !selectedFiles().length;
            });
            get('inventory').addEventListener('click', readInventory);
            get('cancel').addEventListener('click', function () {
                ns.verified.cancel().then(function () { progress('Cancelled'); }).catch(function (err) { progress(err.message); });
            });
        },
        run: async function (file, configuration) {
            fallback = file; stopped = false; jobId = null;
            var runGeneration = ++generation, localJobId = null;
            if (location.protocol === 'file:') return Promise.reject(new Error('Open http://127.0.0.1:8000 for Verified Conversion'));
            var sources = selectedFiles();
            if (!sources.length) return Promise.reject(new Error('Select IFC sources first'));
            configuration.profile = get('profile').value;
            if (get('boundary-obst').checked) configuration.boundary_policy = 'VALIDATED_BOUNDARY_OBST_SINGLE_MESH';
            if (get('reference-case').value) configuration.reference_case = get('reference-case').value;
            if (get('decisions').files.length) configuration.decisions = JSON.parse(await get('decisions').files[0].text());
            if (get('deltas').files.length) configuration.intentional_deltas = JSON.parse(await get('deltas').files[0].text());
            if (get('use-domain').checked) {
                configuration.simulation_domain = {};
                ['xmin','xmax','ymin','ymax','zmin','zmax'].forEach(function (key) { configuration.simulation_domain[key] = Number(get('domain-' + key).value); });
            }
            configuration.scope = {storeys: Array.prototype.filter.call(get('storeys').options, function (o) { return o.selected; }).map(function (o) { return o.value; })};
            if (get('use-bounds').checked) {
                configuration.scope.bounding_box = {};
                ['xmin','xmax','ymin','ymax','zmin','zmax'].forEach(function (key) { configuration.scope.bounding_box[key] = Number(get(key).value); });
            }
            configuration.sources = {common_coordinates: get('common').checked};
            if (sources.length > 1 && !get('common').checked && !get('transform-confirm').checked) return Promise.reject(new Error('Confirm shared coordinates or confirm the source offsets before converting'));
            if (sources.length > 1 && !get('common').checked) {
                configuration.sources.transforms = {};
                sources.forEach(function (source, index) {
                    var values = [0,1,2,3].map(function (axis) { return Number(document.getElementById('verified-transform-' + index + '-' + axis).value); });
                    if (!values.every(isFinite)) throw new Error('Source offsets must be finite');
                    var theta = values[3] * Math.PI / 180, c = Math.cos(theta), s = Math.sin(theta);
                    configuration.sources.transforms[index] = [c,-s,0,values[0],s,c,0,values[1],0,0,1,values[2],0,0,0,1];
                });
            }
            var data = new FormData(); sources.forEach(function (source) { data.append('files', source); });
            if (runGeneration !== generation) throw cancelled();
            data.append('configuration', JSON.stringify(configuration)); get('cancel').disabled = false;
            progress('Uploading…');
            function poll() {
                if (stopped || runGeneration !== generation) return Promise.reject(cancelled());
                return fetch('/api/jobs/' + localJobId).then(response).then(function (job) {
                    if (runGeneration !== generation) throw cancelled();
                    progress(job.state + (job.progress ? ' — ' + job.progress.stage : ''));
                    if (job.state === 'COMPLETED') return fetch('/api/jobs/' + localJobId + '/result').then(response);
                    if (['FAILED','TIMED_OUT','CANCELLED'].indexOf(job.state) !== -1) {
                        var error = new Error(job.error || job.state);
                        error.stage = job.progress ? job.progress.stage : 'VALIDATION';
                        if (job.diagnostics_url) {
                            var link = document.createElement('a'); link.href = job.diagnostics_url;
                            link.textContent = 'Download conversion diagnostics'; link.download = '';
                            get('artifacts').replaceChildren(link);
                        }
                        throw error;
                    }
                    return new Promise(function (resolve) { setTimeout(resolve, 700); }).then(poll);
                });
            }
            return fetch('/api/jobs', {method:'POST',body:data}).then(response).then(function (job) {
                localJobId = job.id;
                if (stopped || runGeneration !== generation) return fetch('/api/jobs/' + localJobId, {method:'DELETE'}).then(function () { throw cancelled(); });
                jobId = localJobId;
                return poll();
            }).then(function (result) {
                if (runGeneration !== generation) throw cancelled();
                progress(result.status);
                get('artifacts').replaceChildren();
                Object.keys(result.artifacts || {}).forEach(function (name) {
                    var link = document.createElement('a'); link.href = result.artifacts[name].url;
                    link.textContent = 'Download ' + name; link.download = ''; link.style.display = 'block'; get('artifacts').appendChild(link);
                });
                result.job_id = localJobId;
                return result; })
                .catch(function (error) { error.jobId = localJobId; throw error; })
                .finally(function () { if (runGeneration === generation) { jobId = null; get('cancel').disabled = true; } });
        }
    };
})(window.IfcFds);
