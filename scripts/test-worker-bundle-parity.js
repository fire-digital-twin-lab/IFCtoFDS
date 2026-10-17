const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

for (const name of ['generate-inline-export-worker.js', 'generate-inline-parse-worker.js']) {
    const generator = fs.readFileSync(path.join(__dirname, name), 'utf8');
    function generate(ending) {
        let output;
        let outputPath;
        const fakeFs = {
            readFileSync(file, encoding) {
                return fs.readFileSync(file, encoding).replace(/\r\n?/g, '\n').replace(/\n/g, ending);
            },
            writeFileSync(file, text) { outputPath = file; output = text; }
        };
        vm.runInNewContext(generator, {__dirname, console: {log() {}},
            require(moduleName) { return moduleName === 'fs' ? fakeFs : require(moduleName); }});
        return {output, outputPath};
    }
    const lf = generate('\n');
    const crlf = generate('\r\n');
    assert.ok(lf.output === crlf.output, name + ' must be identical for LF and CRLF source files');
    assert.ok(fs.readFileSync(lf.outputPath, 'utf8').replace(/\r\n?/g, '\n') === lf.output,
        name + ': committed inline bundle is stale');
}
console.log('Inline worker generation is identical for LF/CRLF sources and matches committed bundles.');
