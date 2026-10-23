(function (root) {
    root.IfcFds = root.IfcFds || {
        core: {},
        fds: {},
        ifc: {},
        viewer: {},
        compare: {},
        legacy: {
            role: "QUICK_PREVIEW",
            authoritative: false,
            description: "Browser-based quick preview and legacy conversion without independent geometric audit."
        },
        verified: {
            role: "VERIFIED_MAPPING",
            authoritative: true,
            description: "Authoritative Python/IfcOpenShell backend with independent 3-tier validation and golden parity."
        }
    };
})(typeof window !== "undefined" ? window : globalThis);
