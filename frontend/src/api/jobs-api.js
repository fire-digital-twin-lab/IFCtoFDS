(function (ns) {
    ns.api.jobs = {
        inventory: function (data) { return ns.api.request('/api/inventory', {method: 'POST', body: data}); },
        submit: function (data) { return ns.api.request('/api/jobs', {method: 'POST', body: data}); },
        read: function (id) { return ns.api.request('/api/jobs/' + id); },
        result: function (id) { return ns.api.request('/api/jobs/' + id + '/result'); },
        cancel: function (id) { return ns.api.request('/api/jobs/' + id, {method: 'DELETE'}); },
        references: function () { return ns.api.request('/api/reference-cases'); }
    };
})(window.IfcFds);
