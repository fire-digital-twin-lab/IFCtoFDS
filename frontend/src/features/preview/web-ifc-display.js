(function (ns) {
    // Display-only IFC geometry loader. Preferred path is a module Web Worker hosting the
    // web-ifc WASM kernel off the main thread. Falls back to a same-page main-thread engine
    // when the worker can't start (e.g. file:// origins, which Chrome blocks from spinning
    // up module workers). Either way the WASM kernel natively applies IfcRelVoidsElement
    // boolean subtractions so walls come out with their window/door openings cut.

    var assetBase = new URL('../../../', document.currentScript.src);
    var LOCAL_WEB_IFC = new URL('vendor/web-ifc/', assetBase).href;

    // -------- worker path ----------------------------------------------------

    function abortError() {
        var error = new Error('Display disposed');
        error.name = 'AbortError';
        return error;
    }

    function createRuntime() {
    var disposed = false;
    var worker = null;
    var workerFailed = false;
    var nextId = 1;
    var pending = {};

    function ensureWorker() {
        if (workerFailed) return null;
        if (worker) return worker;
        try {
            worker = new Worker(new URL('src/workers/web-ifc-display-worker.js', assetBase).href, { type: 'module' });
        } catch (err) {
            console.warn('web-ifc worker init failed, falling back to main thread:', err);
            workerFailed = true;
            return null;
        }
        var activeWorker = worker;
        worker.onmessage = function (event) {
            if (disposed || worker !== activeWorker) return;
            var msg = event.data || {};
            var cb = pending[msg.id];
            if (!cb) return;
            delete pending[msg.id];
            if (msg.type === 'meshes') cb.resolve(msg.meshes);
            else cb.reject(new Error(msg.message || 'web-ifc worker error'));
        };
        worker.onerror = function (event) {
            if (disposed || worker !== activeWorker) return;
            console.warn('web-ifc worker fatal error, falling back to main thread:', event.message || event);
            workerFailed = true;
            try { worker.terminate(); } catch (_) { /* ignore */ }
            worker = null;
            Object.keys(pending).forEach(function (key) {
                pending[key].reject(new Error('worker terminated'));
                delete pending[key];
            });
        };
        return worker;
    }

    function loadViaWorker(arrayBuffer) {
        if (disposed) return Promise.reject(abortError());
        var w = ensureWorker();
        if (!w) return Promise.reject(new Error('worker unavailable'));
        return new Promise(function (resolve, reject) {
            var id = nextId += 1;
            pending[id] = { resolve: resolve, reject: reject };
            try {
                var clone = arrayBuffer.slice(0);
                w.postMessage({ id: id, type: 'load', buffer: clone }, [clone]);
            } catch (err) {
                delete pending[id];
                reject(err);
            }
        });
    }

    return {
        load: loadViaWorker,
        isDisposed: function () { return disposed; },
        dispose: function () {
            if (disposed) return;
            disposed = true;
            if (worker) worker.terminate();
            worker = null;
            Object.keys(pending).forEach(function (key) {
                pending[key].reject(abortError());
                delete pending[key];
            });
        }
    };
    }

    // -------- main-thread fallback path --------------------------------------

    var mainApiPromise = null;

    function initializeApi(api, basePath) {
        api.SetWasmPath(basePath, true);
        if (new URL(basePath).protocol !== 'file:') return api.Init(undefined, true);
        // The vendored browser kernel cannot fetch local file URLs directly.
        // File-mode browsers that permit local reads can use XHR plus a Blob;
        // the kernel then reads the same local WASM through a fetchable URL.
        return new Promise(function (resolve, reject) {
            var request = new XMLHttpRequest();
            request.open('GET', new URL('web-ifc.wasm', basePath).href, true);
            request.responseType = 'arraybuffer';
            request.timeout = 15000;
            request.onload = function () {
                if ((request.status !== 0 && (request.status < 200 || request.status >= 300)) ||
                    !request.response || !request.response.byteLength) {
                    reject(new Error('Local display WASM could not be read'));
                    return;
                }
                var wasmUrl = URL.createObjectURL(new Blob([request.response], {type: 'application/wasm'}));
                Promise.resolve().then(function () {
                    return api.Init(function (name) {
                        return name === 'web-ifc.wasm' ? wasmUrl : new URL(name, basePath).href;
                    }, true);
                }).then(resolve, reject).finally(function () { URL.revokeObjectURL(wasmUrl); });
            };
            request.onerror = request.ontimeout = function () { reject(new Error('Local display WASM access unavailable')); };
            request.send();
        });
    }

    function ensureMainThreadApi() {
        if (mainApiPromise) return mainApiPromise;
        mainApiPromise = (async function () {
            // Strict offline local import compliant with CSP (no new Function or eval)
            var basePath = LOCAL_WEB_IFC;
            var WebIFC;
            try {
                WebIFC = await import(LOCAL_WEB_IFC + 'web-ifc-api.js');
            } catch (localErr) {
                // If on file:// protocol where browsers block local WASM/module fetch without flags, allow fallback
                if (typeof window !== 'undefined' && window.location && window.location.protocol === 'file:') {
                    console.warn('[web-ifc-display] file:// origin restriction detected; falling back to CDN:', localErr);
                    basePath = 'https://cdn.jsdelivr.net/npm/web-ifc@0.0.77/';
                    WebIFC = await import('https://cdn.jsdelivr.net/npm/web-ifc@0.0.77/web-ifc-api.js');
                } else {
                    console.error('[web-ifc-display] Strict offline error: local vendored web-ifc failed to load from ' + LOCAL_WEB_IFC, localErr);
                    throw new Error('Strict offline failure: local vendored web-ifc assets not available in ' + LOCAL_WEB_IFC + '. Verify local assets are present in js/vendor/web-ifc/. Offline mode does not allow CDN fallback: ' + localErr.message);
                }
            }
            var api = new WebIFC.IfcAPI();
            await initializeApi(api, basePath);
            return api;
        })().catch(function (err) {
            console.warn('web-ifc main-thread engine unavailable:', err);
            mainApiPromise = null; // allow another attempt later
            return null;
        });
        return mainApiPromise;
    }

    function loadViaMainThread(arrayBuffer, isDisposed) {
        return ensureMainThreadApi().then(function (api) {
            if (isDisposed()) throw abortError();
            if (!api) return null;
            var bytes = new Uint8Array(arrayBuffer);
            var modelID = api.OpenModel(bytes);
            var meshes = [];
            try {
                api.StreamAllMeshes(modelID, function (flatMesh) {
                    var expressID = flatMesh.expressID;
                    var placed = flatMesh.geometries;
                    var count = placed.size();
                    for (var i = 0; i < count; i += 1) {
                        var entry = readPlacedGeometry(api, modelID, placed.get(i));
                        if (!entry) continue;
                        entry.expressID = expressID;
                        meshes.push(entry);
                    }
                });
            } finally {
                try { api.CloseModel(modelID); } catch (_) { /* ignore */ }
            }
            return meshes;
        });
    }

    function readPlacedGeometry(api, modelID, placed) {
        var geom = null;
        try {
            geom = api.GetGeometry(modelID, placed.geometryExpressID);
            var raw = api.GetVertexArray(geom.GetVertexData(), geom.GetVertexDataSize());
            var idx = api.GetIndexArray(geom.GetIndexData(), geom.GetIndexDataSize());
            var vc = raw.length / 6;
            var positions = new Float32Array(vc * 3);
            var normals = new Float32Array(vc * 3);
            for (var v = 0; v < vc; v += 1) {
                var r = v * 6;
                var w = v * 3;
                positions[w] = raw[r];
                positions[w + 1] = raw[r + 1];
                positions[w + 2] = raw[r + 2];
                normals[w] = raw[r + 3];
                normals[w + 1] = raw[r + 4];
                normals[w + 2] = raw[r + 5];
            }
            var indices = new Uint32Array(idx.length);
            indices.set(idx);
            return {
                positions: positions,
                normals: normals,
                indices: indices,
                color: { r: placed.color.x, g: placed.color.y, b: placed.color.z, a: placed.color.w },
                matrix: Array.prototype.slice.call(placed.flatTransformation)
            };
        } catch (err) {
            console.warn('web-ifc geometry read failed:', err);
            return null;
        } finally {
            if (geom && typeof geom.delete === 'function') {
                try { geom.delete(); } catch (_) { /* ignore */ }
            }
        }
    }

    // -------- public API ------------------------------------------------------

    function WebIfcDisplay() { this.runtime = createRuntime(); }

    WebIfcDisplay.prototype.dispose = function () {
        this.runtime.dispose();
    };

    WebIfcDisplay.prototype.load = function (arrayBuffer) {
        var runtime = this.runtime;
        return runtime.load(arrayBuffer)
            .catch(function (workerErr) {
                if (workerErr.name === 'AbortError' || runtime.isDisposed()) throw abortError();
                return loadViaMainThread(arrayBuffer, runtime.isDisposed);
            })
            .then(function (meshes) {
                if (runtime.isDisposed()) throw abortError();
                return meshes;
            })
            .catch(function (err) {
                if (err.name === 'AbortError') throw err;
                console.warn('web-ifc display load failed:', err);
                return null;
            });
    };

    ns.WebIfcDisplay = WebIfcDisplay;
})(window.IfcFds.ifc);
