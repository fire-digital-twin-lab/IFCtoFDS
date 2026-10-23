// Load the same ordered viewer modules as the browser entrypoint.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
module.exports = function loadViewer(context) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/src/shared/lifecycle.js'), 'utf8'), context);
    for (const file of ['http-client.js', 'jobs-api.js', 'artifacts-api.js', 'geometry-api.js']) {
        vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/src/api', file), 'utf8'), context);
    }
    for (const file of ['geometry-helpers.js', 'camera-controller.js', 'walk-controller.js', 'clipping-controller.js', 'mesh-factory.js', 'geometry-loader.js', 'selection-controller.js', 'appearance-controller.js', 'scene-viewer.js']) {
        vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/src/viewer', file), 'utf8'), context, {filename: file});
    }
};
