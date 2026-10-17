/**
 * Command Bus for IFCtoFDS Research Workbench.
 * Coordinates user actions via the Command Pattern, providing unified execution
 * and undo/redo history stacks.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.commands = root.IfcFds.workbench.commands || {};

    function CommandBus(maxHistory) {
        this._maxHistory = maxHistory || 50;
        this._undoStack = [];
        this._redoStack = [];
        this._listeners = [];
    }

    CommandBus.prototype.execute = function (command) {
        if (!command || typeof command.execute !== 'function') {
            console.error('[CommandBus] Invalid command:', command);
            return false;
        }

        try {
            var result = command.execute();
            if (typeof command.undo === 'function') {
                this._undoStack.push(command);
                if (this._undoStack.length > this._maxHistory) {
                    this._undoStack.shift();
                }
                this._redoStack = [];
            }
            this._notifyHistoryChanged();
            return result !== false;
        } catch (err) {
            console.error('[CommandBus] Execution failed for ' + (command.name || 'unnamed command') + ':', err);
            return false;
        }
    };

    CommandBus.prototype.undo = function () {
        if (!this._undoStack.length) return false;
        var command = this._undoStack.pop();
        try {
            command.undo();
            this._redoStack.push(command);
            this._notifyHistoryChanged();
            return true;
        } catch (err) {
            console.error('[CommandBus] Undo failed for ' + (command.name || 'unnamed command') + ':', err);
            return false;
        }
    };

    CommandBus.prototype.redo = function () {
        if (!this._redoStack.length) return false;
        var command = this._redoStack.pop();
        try {
            command.execute();
            this._undoStack.push(command);
            this._notifyHistoryChanged();
            return true;
        } catch (err) {
            console.error('[CommandBus] Redo failed for ' + (command.name || 'unnamed command') + ':', err);
            return false;
        }
    };

    CommandBus.prototype.canUndo = function () {
        return this._undoStack.length > 0;
    };

    CommandBus.prototype.canRedo = function () {
        return this._redoStack.length > 0;
    };

    CommandBus.prototype.clear = function () {
        this._undoStack = [];
        this._redoStack = [];
        this._notifyHistoryChanged();
    };

    CommandBus.prototype.subscribe = function (listener) {
        if (typeof listener !== 'function') return function () {};
        this._listeners.push(listener);
        var self = this;
        return function () {
            self._listeners = self._listeners.filter(function (l) { return l !== listener; });
        };
    };

    CommandBus.prototype._notifyHistoryChanged = function () {
        var payload = {
            canUndo: this.canUndo(),
            canRedo: this.canRedo(),
            undoCount: this._undoStack.length,
            redoCount: this._redoStack.length
        };
        for (var i = 0; i < this._listeners.length; i++) {
            try {
                this._listeners[i](payload);
            } catch (err) {
                console.error('[CommandBus] Listener error:', err);
            }
        }
    };

    var defaultCommandBus = new CommandBus();

    root.IfcFds.workbench.commands.CommandBus = CommandBus;
    root.IfcFds.workbench.commands.commandBus = defaultCommandBus;

})(typeof window !== 'undefined' ? window : globalThis);
