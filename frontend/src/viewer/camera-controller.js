(function (ns) {
    ns.viewer.installCameraController = function (SceneViewer, helpers) {
        var toThree = helpers.toThree;

        SceneViewer.prototype.setView = function (direction) {
            this.ifcGroup.updateMatrixWorld(true);
            this.fdsGroup.updateMatrixWorld(true);
            var box = new THREE.Box3();
            if (this.ifcGroup.visible) box.expandByObject(this.ifcGroup);
            if (this.fdsGroup.visible) box.expandByObject(this.fdsGroup);
            if (box.isEmpty()) {
                box.expandByObject(this.ifcGroup);
                box.expandByObject(this.fdsGroup);
            }
            if (box.isEmpty()) return;
            var center = box.getCenter(new THREE.Vector3());
            var size = box.getSize(new THREE.Vector3());
            var dist = Math.max(size.x, size.y, size.z, 1) * 1.6;

            this.setNavigationMode('orbit');
            this.controls.target.copy(center);
            switch (direction) {
                case 'front':
                    this.camera.position.set(center.x, center.y, center.z + dist);
                    break;
                case 'back':
                    this.camera.position.set(center.x, center.y, center.z - dist);
                    break;
                case 'left':
                    this.camera.position.set(center.x - dist, center.y, center.z);
                    break;
                case 'right':
                    this.camera.position.set(center.x + dist, center.y, center.z);
                    break;
                case 'top':
                    this.camera.position.set(center.x, center.y + dist, center.z);
                    break;
                case 'bottom':
                    this.camera.position.set(center.x, center.y - dist, center.z);
                    break;
                case 'iso':
                default:
                    this.camera.position.set(
                        center.x + dist * 0.7,
                        center.y + dist * 0.55,
                        center.z + dist * 0.7
                    );
                    break;
            }
            this.camera.near = Math.max(dist / 500, 0.02);
            this.camera.far = dist * 50;
            this.camera.updateProjectionMatrix();
            this.controls.update();
        };

        SceneViewer.prototype.orbitByKey = function (direction, modifiers) {
            if (this.navigationMode !== 'orbit' || !this.controls) return false;
            modifiers = modifiers || {};
            var camera = this.camera;
            var target = this.controls.target;
            var offset = new THREE.Vector3().subVectors(camera.position, target);
            var radius = offset.length();
            var spherical = new THREE.Spherical().setFromVector3(offset);
            var rotateStep = Math.PI / 36; // 5°
            var dollyStep = 1.12;
            var panStep = radius * 0.05;

            if (modifiers.shift && (direction === 'up' || direction === 'down')) {
                // Shift + vertical → dolly. Up zooms in, down zooms out.
                offset.multiplyScalar(direction === 'up' ? 1 / dollyStep : dollyStep);
            } else if (modifiers.shift && (direction === 'left' || direction === 'right')) {
                // Shift + horizontal → strafe the target & camera together along the camera's
                // right vector so the orbit pivot itself moves.
                var right = new THREE.Vector3();
                camera.getWorldDirection(right);
                right.cross(camera.up).normalize().multiplyScalar(direction === 'right' ? panStep : -panStep);
                target.add(right);
                camera.position.add(right);
                this.controls.update();
                return true;
            } else if (direction === 'left') {
                spherical.theta -= rotateStep;
                offset.setFromSpherical(spherical);
            } else if (direction === 'right') {
                spherical.theta += rotateStep;
                offset.setFromSpherical(spherical);
            } else if (direction === 'up') {
                spherical.phi = Math.max(0.05, spherical.phi - rotateStep);
                offset.setFromSpherical(spherical);
            } else if (direction === 'down') {
                spherical.phi = Math.min(Math.PI - 0.05, spherical.phi + rotateStep);
                offset.setFromSpherical(spherical);
            } else {
                return false;
            }

            camera.position.copy(target).add(offset);
            camera.lookAt(target);
            this.controls.update();
            return true;
        };

        SceneViewer.prototype.fitToWorldBox = function () {
            this.ifcGroup.updateMatrixWorld(true);
            var box = new THREE.Box3().expandByObject(this.ifcGroup);
            if (box.isEmpty()) return;
            var center = box.getCenter(new THREE.Vector3());
            var size = box.getSize(new THREE.Vector3());
            var span = Math.max(size.x, size.y, size.z, 1);
            this.walkFloorY = box.min.y;
            this.controls.target.copy(center);
            this.camera.position.set(center.x + span * 1.2, center.y + span * 0.9, center.z + span * 1.2);
            this.camera.near = Math.max(span / 200, 0.05);
            this.camera.far = span * 50;
            this.camera.updateProjectionMatrix();
            this.controls.update();
        };

        SceneViewer.prototype.fitToBounds = function (bounds) {
            if (!bounds) return;
            this.walkFloorY = bounds.zmin;
            var center = {
                x: (bounds.xmin + bounds.xmax) / 2,
                y: (bounds.ymin + bounds.ymax) / 2,
                z: (bounds.zmin + bounds.zmax) / 2
            };
            var span = Math.max(bounds.xmax - bounds.xmin, bounds.ymax - bounds.ymin, bounds.zmax - bounds.zmin, 1);
            var threeCenter = toThree(center.x, center.y, center.z);
            this.controls.target.copy(threeCenter);
            this.camera.position.set(threeCenter.x + span * 1.2, threeCenter.y + span * 0.9, threeCenter.z + span * 1.2);
            this.camera.near = Math.max(span / 200, 0.05);
            this.camera.far = span * 50;
            this.camera.updateProjectionMatrix();
            this.controls.update();
        };

        SceneViewer.prototype.resetCamera = function () {
            this.setNavigationMode('orbit');
            var box = new THREE.Box3();
            if (this.fdsGroup.visible) box.expandByObject(this.fdsGroup);
            if (this.ifcGroup.visible) box.expandByObject(this.ifcGroup);
            if (box.isEmpty()) {
                box.expandByObject(this.fdsGroup);
                box.expandByObject(this.ifcGroup);
            }
            if (!box.isEmpty()) {
                var center = box.getCenter(new THREE.Vector3());
                var size = box.getSize(new THREE.Vector3());
                var span = Math.max(size.x, size.y, size.z, 1);
                this.controls.target.copy(center);
                this.camera.position.set(center.x + span * 1.2, center.y + span * 0.9, center.z + span * 1.2);
                this.controls.update();
            }
        };

    };
})(window.IfcFds);
