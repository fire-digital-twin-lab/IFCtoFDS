(function (ns) {
    'use strict';
    var jobId = null, stopped = false, fallback = null;
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
                option.textContent = storey.name + ' [' + storey.source_id.slice(0, 8) + ']';
                get('storeys').appendChild(option);
            });
            progress(inventory.total_elements + ' entities in ' + inventory.sources.length + ' sources');
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
        init: function () {
            get('sources').addEventListener('change', function () {
                transformInputs(); get('storeys').replaceChildren();
                document.getElementById('convert-verified').disabled = !selectedFiles().length;
            });
            get('inventory').addEventListener('click', readInventory);
            get('cancel').addEventListener('click', function () {
                stopped = true;
                if (jobId) fetch('/api/jobs/' + jobId, {method: 'DELETE'}).then(response).then(function () { progress('Cancelled'); }).catch(function (err) { progress(err.message); });
            });
        },
        run: function (file, configuration) {
            fallback = file; stopped = false; jobId = null;
            if (location.protocol === 'file:') return Promise.reject(new Error('Open http://127.0.0.1:8000 for Verified Conversion'));
            var sources = selectedFiles();
            if (!sources.length) return Promise.reject(new Error('Select IFC sources first'));
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
            data.append('configuration', JSON.stringify(configuration)); get('cancel').disabled = false;
            progress('Uploading…');
            function poll() {
                if (stopped) return Promise.reject(new Error('Conversion cancelled'));
                return fetch('/api/jobs/' + jobId).then(response).then(function (job) {
                    progress(job.state);
                    if (job.state === 'COMPLETED') return fetch('/api/jobs/' + jobId + '/result').then(response);
                    if (['FAILED','TIMED_OUT','CANCELLED'].indexOf(job.state) !== -1) throw new Error(job.error || job.state);
                    return new Promise(function (resolve) { setTimeout(resolve, 700); }).then(poll);
                });
            }
            return fetch('/api/jobs', {method:'POST',body:data}).then(response).then(function (job) {
                jobId = job.id;
                if (stopped) return fetch('/api/jobs/' + jobId, {method:'DELETE'}).then(function () { throw new Error('Conversion cancelled'); });
                return poll();
            }).then(function (result) { progress(result.status); return result; })
                .finally(function () { get('cancel').disabled = true; });
        }
    };
})(window.IfcFds);
