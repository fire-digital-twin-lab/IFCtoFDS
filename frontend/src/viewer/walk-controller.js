(function (ns) {
    ns.viewer.installWalkController = function (SceneViewer, helpers) {
        var collectWalkTargets = helpers.collectWalkTargets;
        var walkHitHasUpwardNormal = helpers.walkHitHasUpwardNormal;
        var walkHitIsPassable = helpers.walkHitIsPassable;

        SceneViewer.prototype.setNavigationModeChangeHandler = function (handler) {
            this.onNavigationModeChange = handler || function () {};
        };

        SceneViewer.prototype.setNavigationMode = function (mode) {
            var nextMode = mode === 'walk' && this.walkControls ? 'walk' : 'orbit';
            if (nextMode === this.navigationMode) {
                if (nextMode === 'walk' && this.walkPlaced && !this.walkControls.isLocked) this.walkControls.lock();
                return;
            }

            this.navigationMode = nextMode;
            this.controls.enabled = nextMode === 'orbit';
            this.clearWalkMovement();
            this.walkVelocityY = 0;
            this.container.classList.toggle('is-walking', nextMode === 'walk');
            this.container.classList.toggle('is-walk-awaiting', nextMode === 'walk');
            this.container.classList.remove('is-walk-placed');
            this.clearHover();

            if (nextMode === 'walk') {
                this.walkSavedCamera = {
                    position: this.camera.position.clone(),
                    quaternion: this.camera.quaternion.clone(),
                    target: this.controls.target.clone()
                };
                this.walkPlaced = false;
                this.setWalkStatus('Click a floor or stair surface to begin.');
            } else {
                if (this.walkControls.isLocked) this.walkControls.unlock();
                this.walkPlaced = false;
                if (this.walkSavedCamera) {
                    this.camera.position.copy(this.walkSavedCamera.position);
                    this.camera.quaternion.copy(this.walkSavedCamera.quaternion);
                    this.controls.target.copy(this.walkSavedCamera.target);
                    this.walkSavedCamera = null;
                    this.controls.update();
                } else {
                    this.syncOrbitTargetToCamera();
                }
                this.setWalkStatus('');
            }
            this.onNavigationModeChange(nextMode);
        };

        SceneViewer.prototype.positionWalkCamera = function () {
            var lookDirection = this.camera.getWorldDirection(new THREE.Vector3());
            lookDirection.y = 0;
            if (lookDirection.lengthSq() < 1e-8) lookDirection.set(0, 0, -1);
            lookDirection.normalize();

            var target = this.controls.target.clone();
            var horizontalDistance = Math.max(3, Math.hypot(
                this.camera.position.x - target.x,
                this.camera.position.z - target.z
            ));
            this.camera.position.set(
                target.x - lookDirection.x * horizontalDistance,
                this.walkFloorY + this.walkEyeHeight,
                target.z - lookDirection.z * horizontalDistance
            );
            this.camera.lookAt(new THREE.Vector3(target.x, this.camera.position.y, target.z));
        };

        SceneViewer.prototype.syncOrbitTargetToCamera = function () {
            var direction = this.camera.getWorldDirection(new THREE.Vector3());
            this.controls.target.copy(this.camera.position).add(direction.multiplyScalar(5));
            this.controls.update();
        };

        SceneViewer.prototype.handleWalkUnlock = function () {
            if (this.navigationMode === 'walk') this.setNavigationMode('orbit');
        };

        SceneViewer.prototype.handleWalkKey = function (pressed, event) {
            if (this.navigationMode !== 'walk') return;
            var key = String(event.key || '').toLowerCase();
            var handled = true;
            if (key === 'w' || key === 'arrowup') this.walkMovement.forward = pressed;
            else if (key === 's' || key === 'arrowdown') this.walkMovement.backward = pressed;
            else if (key === 'a' || key === 'arrowleft') this.walkMovement.left = pressed;
            else if (key === 'd' || key === 'arrowright') this.walkMovement.right = pressed;
            else if (key === ' ') this.walkMovement.jump = pressed;
            else if (key === 'shift') this.walkMovement.fast = pressed;
            else handled = false;
            if (handled) event.preventDefault();
        };

        SceneViewer.prototype.clearWalkMovement = function () {
            Object.keys(this.walkMovement).forEach(function (key) {
                this.walkMovement[key] = false;
            }, this);
        };

        SceneViewer.prototype.updateWalkMovement = function (delta) {
            if (!this.walkPlaced || !delta) return;

            var forward = this.camera.getWorldDirection(new THREE.Vector3());
            forward.y = 0;
            if (forward.lengthSq() < 1e-9) forward.set(0, 0, -1);
            forward.normalize();
            var right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize();
            var move = new THREE.Vector3();

            if (this.walkMovement.forward) move.add(forward);
            if (this.walkMovement.backward) move.sub(forward);
            if (this.walkMovement.right) move.add(right);
            if (this.walkMovement.left) move.sub(right);
            if (move.lengthSq()) {
                move.normalize().multiplyScalar(this.walkSpeed * (this.walkMovement.fast ? this.walkRunMultiplier : 1) * delta);
            }

            var cameraPosition = this.camera.position;
            var horizontal = this.resolveWalkHorizontal(cameraPosition, cameraPosition.x + move.x, cameraPosition.z + move.z);
            var currentFloorY = cameraPosition.y - this.walkEyeHeight;
            var floorY = this.walkRaycastDown(horizontal.x, horizontal.z, cameraPosition.y + this.walkStepHeight + 0.05);
            var surfaceY = floorY !== null && floorY <= currentFloorY + this.walkStepHeight + 0.02
                ? floorY
                : this.walkDomainFloor();
            var targetEyeY = surfaceY + this.walkEyeHeight;

            this.walkVelocityY -= this.walkGravity * delta;
            var nextY = cameraPosition.y + this.walkVelocityY * delta;
            if (nextY <= targetEyeY) {
                nextY = targetEyeY;
                this.walkVelocityY = 0;
                if (this.walkMovement.jump) this.walkVelocityY = 4;
            }

            this.camera.position.set(horizontal.x, nextY, horizontal.z);
        };

        SceneViewer.prototype.walkCollisionTargets = function () {
            var targets = [];
            var hasFdsSolids = this.obstGroup.children.length || this.geomGroup.children.length;
            if (hasFdsSolids) {
                collectWalkTargets(this.obstGroup, targets);
                collectWalkTargets(this.geomGroup, targets);
            } else {
                collectWalkTargets(this.ifcSolidGroup, targets, function (node) {
                    return node.userData.ifcType !== 'IFCDOOR' && node.userData.ifcType !== 'IFCWINDOW';
                });
            }
            return targets;
        };

        SceneViewer.prototype.walkDomainFloor = function () {
            return Number.isFinite(this.walkFloorY) ? this.walkFloorY : 0;
        };

        SceneViewer.prototype.walkRaycastDown = function (x, z, fromY) {
            this.scene.updateMatrixWorld(true);
            this.walkRaycaster.set(new THREE.Vector3(x, fromY, z), new THREE.Vector3(0, -1, 0));
            this.walkRaycaster.far = 200;
            var hits = this.walkRaycaster.intersectObjects(this.walkCollisionTargets(), false);
            for (var index = 0; index < hits.length; index += 1) {
                if (walkHitHasUpwardNormal(hits[index], 0.2)) return hits[index].point.y;
            }
            return null;
        };

        SceneViewer.prototype.resolveWalkHorizontal = function (from, toX, toZ) {
            var dx = toX - from.x;
            var dz = toZ - from.z;
            var stepLength = Math.hypot(dx, dz);
            if (stepLength < 1e-6) return { x: from.x, z: from.z };

            this.scene.updateMatrixWorld(true);
            var direction = new THREE.Vector3(dx / stepLength, 0, dz / stepLength);
            var probeYs = [from.y, from.y - this.walkEyeHeight * 0.5];
            var targets = this.walkCollisionTargets();
            var holeBoxes = this.walkHoleBboxes();
            var minimumHit = Infinity;

            probeYs.forEach(function (probeY) {
                this.walkRaycaster.set(new THREE.Vector3(from.x, probeY, from.z), direction);
                this.walkRaycaster.far = stepLength + this.walkRadius;
                var hits = this.walkRaycaster.intersectObjects(targets, false);
                // First passable hit wins. Skip:
                //  * Door closure OBSTs (IFC_DOOR SURF) — the door is openable, walk through it.
                //  * Wall OBST hits whose hit point falls inside any &HOLE volume — the HOLE
                //    declares that this region of the wall is carved away in the FDS namelist,
                //    so the walker should pass straight through it in the viewer too.
                for (var i = 0; i < hits.length; i += 1) {
                    if (walkHitIsPassable(hits[i], holeBoxes)) continue;
                    if (hits[i].distance < minimumHit) minimumHit = hits[i].distance;
                    break;
                }
            }, this);

            var allowed = minimumHit < Infinity ? Math.max(0, minimumHit - this.walkRadius) : stepLength;
            return {
                x: from.x + direction.x * allowed,
                z: from.z + direction.z * allowed
            };
        };

        SceneViewer.prototype.walkHoleBboxes = function () {
            var boxes = [];
            if (!this.holeGroup || !this.holeGroup.visible) return boxes;
            this.holeGroup.updateMatrixWorld(true);
            this.holeGroup.children.forEach(function (node) {
                if (!node.isMesh && !node.children.length) return;
                var box = new THREE.Box3().setFromObject(node);
                if (!box.isEmpty()) boxes.push(box);
            });
            return boxes;
        };

        SceneViewer.prototype.placeWalkerFromClick = function (clientX, clientY) {
            var rect = this.renderer.domElement.getBoundingClientRect();
            this.mouse.x = ((clientX - rect.left) / rect.width) * 2 - 1;
            this.mouse.y = -((clientY - rect.top) / rect.height) * 2 + 1;
            this.raycaster.setFromCamera(this.mouse, this.camera);
            this.scene.updateMatrixWorld(true);

            var hits = this.raycaster.intersectObjects(this.walkCollisionTargets(), false);
            // Previous logic placed the walker on the very first hit with an upward-facing
            // normal. That puts the walker on the *top* of whatever the cursor crossed first —
            // a wall's top capping face, a beam, a door header, or a thin door-closure OBST —
            // instead of on the floor of the room the user is pointing at. Now we use the
            // closest hit only as an (x, z) target, then raycast straight DOWN from above to
            // find the actual walkable floor below that point.
            if (hits.length) {
                var anchor = hits[0].point.clone();
                var startY = anchor.y + 50; // well above any reasonable building height
                var floorY = this.walkRaycastDown(anchor.x, anchor.z, startY);
                if (floorY !== null) {
                    this.placeWalkerAt(new THREE.Vector3(anchor.x, floorY, anchor.z));
                    return true;
                }
                // Fallback: drop to the model's natural floor extent.
                this.placeWalkerAt(new THREE.Vector3(anchor.x, this.walkDomainFloor(), anchor.z));
                return true;
            }

            var direction = this.raycaster.ray.direction;
            if (direction.y < -1e-6) {
                var distance = (this.walkDomainFloor() - this.raycaster.ray.origin.y) / direction.y;
                if (distance > 0) {
                    this.placeWalkerAt(this.raycaster.ray.origin.clone().add(direction.clone().multiplyScalar(distance)));
                    return true;
                }
            }

            this.setWalkStatus('No walkable surface there. Click a floor or stair.');
            return false;
        };

        SceneViewer.prototype.placeWalkerAt = function (point) {
            var eye = new THREE.Vector3(point.x, point.y + this.walkEyeHeight, point.z);
            var direction = this.camera.getWorldDirection(new THREE.Vector3());
            direction.y = 0;
            if (direction.lengthSq() < 1e-9) direction.set(0, 0, -1);
            direction.normalize();

            this.camera.position.copy(eye);
            this.camera.lookAt(eye.clone().add(direction));
            this.walkPlaced = true;
            this.walkVelocityY = 0;
            this.container.classList.remove('is-walk-awaiting');
            this.container.classList.add('is-walk-placed');
            this.setWalkStatus('Walking');
            if (!this.walkControls.isLocked) this.walkControls.lock();
        };

        SceneViewer.prototype.setWalkStatus = function (text) {
            var hud = document.getElementById('walk-hud');
            var status = document.getElementById('walk-hud-status');
            if (!hud || !status) return;
            status.textContent = text;
            hud.hidden = !text;
        };

    };
})(window.IfcFds);
