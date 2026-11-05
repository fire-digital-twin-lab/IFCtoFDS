'use strict';
// Browser-side regression: never read persisted API credentials.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.resolve(__dirname, '../js/verified-workflow.js'), 'utf8');
const context = {
    IfcFds: {},
    localStorage: {
        getItem() { throw new Error('Persistent credential storage must not be read'); },
        setItem() { throw new Error('Persistent credential storage must not be written'); }
    },
    fetch: async (url, options) => ({url, headers: options.headers})
};
context.window = context;
vm.runInNewContext(source, context, {filename: 'verified-workflow.js'});
const verified = context.IfcFds.verified;

assert.equal(verified.getAuthHeaders({Accept: 'application/json'})['x-api-key'], undefined);
verified.setApiKey('  ephemeral-secret  ');
const headers = verified.getAuthHeaders({Accept: 'application/json'});
assert.equal(headers['x-api-key'], 'ephemeral-secret');
assert.equal(headers.Accept, 'application/json');
assert.equal(verified.getAuthHeaders({})['x-api-key'], 'ephemeral-secret');

verified.authFetch('/api/health', {headers: {Accept: 'application/json'}}).then(response => {
    assert.equal(response.headers['x-api-key'], 'ephemeral-secret');
    verified.setApiKey('');
    assert.equal(verified.getAuthHeaders({})['x-api-key'], undefined);
    context.IFCFDS_API_KEY = 'in-memory-global';
    assert.equal(verified.getAuthHeaders({})['x-api-key'], 'in-memory-global');
    console.log('API key remains ephemeral and does not access localStorage.');
}).catch(error => {
    console.error(error);
    process.exitCode = 1;
});
