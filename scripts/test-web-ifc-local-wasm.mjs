// Real vendored WASM/IFC, with local-file transport emulated in Node.
// This is not a browser acceptance result.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath, pathToFileURL} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.join(root, 'frontend/src/features/preview/web-ifc-display.js');
const wasm = fs.readFileSync(path.join(root, 'frontend/vendor/web-ifc/web-ifc.wasm'));
const requests = [], released = [];
class LocalURL extends URL {
    static createObjectURL(blob) {return URL.createObjectURL(blob);}
    static revokeObjectURL(url) {released.push(url); URL.revokeObjectURL(url);}
}
class LocalXHR {
    open(method, url) {assert.equal(method, 'GET'); this.url = url;}
    send() {
        requests.push(this.url);
        assert.equal(this.url, pathToFileURL(path.join(root, 'frontend/vendor/web-ifc/web-ifc.wasm')).href);
        this.status = 0;
        this.response = wasm.buffer.slice(wasm.byteOffset, wasm.byteOffset + wasm.byteLength);
        queueMicrotask(() => this.onload());
    }
}
const context = vm.createContext({URL: LocalURL, Blob, XMLHttpRequest: LocalXHR, console,
    fetch, WebAssembly, TextDecoder, TextEncoder, setTimeout, clearTimeout, performance,
    navigator: {userAgent: 'Chrome/120.0'}, crossOriginIsolated: true,
    document: {currentScript: {src: pathToFileURL(source).href}},
    Worker: class {constructor() {throw new Error('File-mode module worker unavailable');}}});
context.window = context;
context.self = context;
context.IfcFds = {ifc: {}};
const vendorPath = path.join(root, 'frontend/vendor/web-ifc/web-ifc-api.js');
const vendor = new vm.SourceTextModule(fs.readFileSync(vendorPath, 'utf8'), {
    context, identifier: pathToFileURL(vendorPath).href
});
await vendor.link(() => {throw new Error('Unexpected external dependency');});
await vendor.evaluate();
const script = new vm.Script(fs.readFileSync(source, 'utf8'), {
    filename: source,
    importModuleDynamically: specifier => {
        assert.equal(specifier, pathToFileURL(path.join(root, 'frontend/vendor/web-ifc/web-ifc-api.js')).href);
        return vendor;
    }
});
script.runInContext(context);
const bytes = fs.readFileSync(path.join(root, 'tests/browser/box.ifc'));
const display = new context.IfcFds.ifc.WebIfcDisplay();
const meshes = await display.load(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
assert.ok(meshes && meshes.length > 0, 'Real local WASM must produce IFC geometry');
assert.ok(meshes.every(mesh => mesh.positions.length > 0 && mesh.positions.every(Number.isFinite)));
assert.equal(requests.length, 1);
assert.equal(released.length, 1, 'Release the temporary WASM Blob URL');
display.dispose();
console.log('Real vendored WASM loaded through local-file fallback and produced IFC meshes. Browser acceptance remains separate.');
