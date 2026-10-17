/**
 * DOM Element Cache for IFCtoFDS Research Workbench.
 * Caches all static DOM lookups to avoid querySelector overhead.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.ui = root.IfcFds.ui || {};

    var els = {};

    function cacheElements() {
        els.viewer = document.getElementById('viewer');
        els.ifcFile = document.getElementById('ifc-file');
        els.toggleTheme = document.getElementById('toggle-theme');
        els.toggleWalk = document.getElementById('toggle-walk');
        els.openHelp = document.getElementById('open-help');
        els.footerHelp = document.getElementById('footer-help');
        els.helpModal = document.getElementById('help-modal');
        els.closeHelp = document.getElementById('close-help');
        els.resetCamera = document.getElementById('reset-camera');
        els.convertIfc = document.getElementById('convert-ifc');
        els.convertSelectedObst = document.getElementById('convert-selected-obst');
        els.saveFds = document.getElementById('save-fds');
        els.fdsSourceName = document.getElementById('fds-source-name');
        els.ifcSourceName = document.getElementById('ifc-source-name');
        els.diagnostics = document.getElementById('diagnostics');
        els.inspectCard = document.getElementById('inspect-card');
        els.inspectTitle = document.getElementById('inspect-title');
        els.inspectBody = document.getElementById('inspect-body');
        els.countMeshes = document.getElementById('count-meshes');
        els.countObsts = document.getElementById('count-obsts');
        els.countVents = document.getElementById('count-vents');
        els.countGeoms = document.getElementById('count-geoms');
        els.countTriangles = document.getElementById('count-triangles');
        els.countIfc = document.getElementById('count-ifc');
        els.countIfcConvertible = document.getElementById('count-ifc-convertible');
        els.ifcMapping = document.getElementById('ifc-mapping');
        els.fdsOpacity = document.getElementById('fds-opacity');
        els.ifcOpacity = document.getElementById('ifc-opacity');
        els.meshCellSize = document.getElementById('mesh-cell-size');
        els.voxelSize = document.getElementById('voxel-size');
        els.openingThickening = document.getElementById('opening-thickening');
        els.openingVoxelPolicy = document.getElementById('opening-voxel-policy');
        els.includeFillSolids = document.getElementById('include-fill-solids');
        els.includeReviewSolids = document.getElementById('include-review-solids');
        els.conversionApproach = document.getElementById('conversion-approach');
        els.obstThreshold = document.getElementById('obst-threshold');
        els.obstThresholdVal = document.getElementById('obst-threshold-val');
        els.openCredits = document.getElementById('open-credits');
        els.creditsModal = document.getElementById('credits-modal');
        els.closeCredits = document.getElementById('close-credits');
        els.openAudit = document.getElementById('open-audit');
        els.saveManifest = document.getElementById('save-manifest');
        els.convertVerified = document.getElementById('convert-verified');
        els.auditModal = document.getElementById('audit-modal');
        els.closeAudit = document.getElementById('close-audit');
        els.auditBody = document.getElementById('audit-body');
        els.backendStatusIndicator = document.getElementById('backend-status-indicator');
        els.backendStatusText = document.getElementById('backend-status-text');
        els.ifcLoading = document.getElementById('ifc-loading');
        els.ifcLoadingTitle = document.getElementById('ifc-loading-title');
        els.ifcLoadingPercent = document.getElementById('ifc-loading-percent');
        els.ifcLoadingFill = document.getElementById('ifc-loading-fill');
        els.ifcLoadingStage = document.getElementById('ifc-loading-stage');
        els.saveProcessed = document.getElementById('save-processed');
        els.showIfcEdges = document.getElementById('show-ifc-edges');
        els.showGrid = document.getElementById('show-grid');
        els.showStructure = document.getElementById('show-structure');
        els.showFills = document.getElementById('show-fills');
        els.showOther = document.getElementById('show-other');
        els.showObst = document.getElementById('show-obst');
        els.showHole = document.getElementById('show-hole');
        els.showGeom = document.getElementById('show-geom');
        els.deleteSelected = document.getElementById('delete-selected-ifc');
        els.undoLast = document.getElementById('undo-last');
        els.clipPanel = document.getElementById('clip-panel');
        els.clipReset = document.getElementById('clip-reset');
        els.clipSliders = {
            xmin: document.getElementById('clip-xmin'),
            xmax: document.getElementById('clip-xmax'),
            ymin: document.getElementById('clip-ymin'),
            ymax: document.getElementById('clip-ymax'),
            zmin: document.getElementById('clip-zmin'),
            zmax: document.getElementById('clip-zmax')
        };
        els.clipInputs = {
            xmin: document.getElementById('clip-xmin-val'),
            xmax: document.getElementById('clip-xmax-val'),
            ymin: document.getElementById('clip-ymin-val'),
            ymax: document.getElementById('clip-ymax-val'),
            zmin: document.getElementById('clip-zmin-val'),
            zmax: document.getElementById('clip-zmax-val')
        };
        els.modeTabVerified = document.getElementById('mode-tab-verified');
        els.modeTabQuick = document.getElementById('mode-tab-quick');
        els.containerVerified = document.getElementById('container-verified');
        els.containerQuick = document.getElementById('container-quick');
        els.verifiedWorkflowBanner = document.getElementById('verified-workflow-banner');
        els.quickWorkflowBanner = document.getElementById('quick-workflow-banner');
        els.verifiedStoreys = document.getElementById('verified-storeys');
        els.verifiedUseDomain = document.getElementById('verified-use-domain');
        els.verifiedDomainWarning = document.getElementById('verified-domain-warning');
        els.verifiedForceGeom = document.getElementById('verified-force-geom');
        els.verifiedCellSize = document.getElementById('verified-cell-size');
        els.domainEstCells = document.getElementById('domain-est-cells');
        els.domainEstBudget = document.getElementById('domain-est-budget');
        els.domainDimensionsText = document.getElementById('domain-dimensions-text');
        els.auditDrawer = document.getElementById('audit-drawer');
        els.toggleDrawer = document.getElementById('toggle-drawer');
        els.closeInspector = document.getElementById('close-inspector');
        return els;
    }

    root.IfcFds.ui.domCache = {
        init: cacheElements,
        els: els
    };
})(window);
