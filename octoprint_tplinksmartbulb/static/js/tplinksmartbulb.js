/*
 * View model for OctoPrint-TPLinkSmartBulb
 *
 * Author: jneilliii
 * License: AGPLv3
 */
$(function() {
    function tplinksmartbulbViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];
		self.loginState = parameters[1];

		self.arrSmartBulbs = ko.observableArray();
		self.isPrinting = ko.observable(false);
		self.selectedBulb = ko.observable();
		self.processing = ko.observableArray([]);
		self.energy_data = function(data){
			var output = data.label() + '<br/>';
			var energy_data = ko.toJS(data.emeter);
			for (x in energy_data){output += x + ': ' + energy_data[x] + '<br/>'};
			return output;
		}
		
		self.onBeforeBinding = function() {		
			self.arrSmartBulbs(self.settings.settings.plugins.tplinksmartbulb.arrSmartBulbs());
        }
		
		self.onAfterBinding = function() {
			self.checkStatuses();
		}

        self.onEventSettingsUpdated = function(payload) {
			self.arrSmartBulbs(self.settings.settings.plugins.tplinksmartbulb.arrSmartBulbs());
		}
		
		self.onEventPrinterStateChanged = function(payload) {
			if (payload.state_id == "PRINTING" || payload.state_id == "PAUSED"){
				self.isPrinting(true);
			} else {
				self.isPrinting(false);
			}
		}
		
		self.cancelClick = function(data) {
			self.processing.remove(data.ip());
		}
		
		self.editBulb = function(data) {
			self.selectedBulb(data);
			$("#TPLinkBulbEditor").modal("show");
		}
		
		self.addBulb = function() {
			self.selectedBulb({'ip':ko.observable(''),
									'label':ko.observable(''),
									'icon':ko.observable('icon-lightbulb'),
									'displayWarning':ko.observable(true),
									'warnPrinting':ko.observable(false),
									'gcodeEnabled':ko.observable(false),
									'gcodeOnDelay':ko.observable(0),
									'gcodeOffDelay':ko.observable(0),
									'autoConnect':ko.observable(true),
									'autoConnectDelay':ko.observable(10.0),
									'autoDisconnect':ko.observable(true),
									'autoDisconnectDelay':ko.observable(0),
									'sysCmdOn':ko.observable(false),
									'sysRunCmdOn':ko.observable(''),
									'sysCmdOnDelay':ko.observable(0),
									'sysCmdOff':ko.observable(false),
									'sysRunCmdOff':ko.observable(''),
									'sysCmdOffDelay':ko.observable(0),
									'currentState':ko.observable('unknown'),
									'btnColor':ko.observable('#808080')});
			self.settings.settings.plugins.tplinksmartbulb.arrSmartBulbs.push(self.selectedBulb());
			$("#TPLinkBulbEditor").modal("show");
		}
		
		self.removePlug = function(row) {
			self.settings.settings.plugins.tplinksmartbulb.arrSmartBulbs.remove(row);
		}
		
		self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "tplinksmartbulb") {
                return;
            }
			
			bulb = ko.utils.arrayFirst(self.settings.settings.plugins.tplinksmartbulb.arrSmartBulbs(),function(item){
				return item.ip() === data.ip;
				}) || {'ip':data.ip,'currentState':'unknown','btnColor':'#808080'};
			
			if (bulb.currentState != data.currentState) {
				bulb.currentState(data.currentState)
				switch(data.currentState) {
					case "on":
						break;
					case "off":
						break;
					default:
						new PNotify({
							title: 'TP-Link SmartBulb Error',
							text: 'Status ' + bulb.currentState() + ' for ' + bulb.ip() + '. Double check IP Address\\Hostname in TPLinkSmartBulb Settings.',
							type: 'error',
							hide: true
							});
				self.settings.saveData();
				}
			}
			self.processing.remove(data.ip);
        };
		
		self.toggleBulb = function(data) {
			self.processing.push(data.ip());
			switch(data.currentState()){
				case "on":
					self.turnOff(data);
					break;
				case "off":
					self.turnOn(data);
					break;
				default:
					self.checkStatus(data.ip());
			}
		}
		
		self.turnOn = function(data) {
			self.sendTurnOn(data);
		}
		
		self.sendTurnOn = function(data) {
            $.ajax({
                url: API_BASEURL + "plugin/tplinksmartbulb",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "turnOn",
					ip: data.ip()
                }),
                contentType: "application/json; charset=UTF-8"
            });
        };

    	self.turnOff = function(data) {
			if((data.displayWarning() || (self.isPrinting() && data.warnPrinting())) && !$("#TPLinkSmartPlugWarning").is(':visible')){
				self.selectedBulb(data);
				$("#TPLinkSmartBulbWarning").modal("show");
			} else {
				$("#TPLinkSmartBulbWarning").modal("hide");
				self.sendTurnOff(data);
			}
        }; 
		
		self.sendTurnOff = function(data) {
			$.ajax({
			url: API_BASEURL + "plugin/tplinksmartbulb",
			type: "POST",
			dataType: "json",
			data: JSON.stringify({
				command: "turnOff",
				ip: data.ip()
			}),
			contentType: "application/json; charset=UTF-8"
			});		
		}
		
		self.checkStatus = function(bulbip) {
            $.ajax({
                url: API_BASEURL + "plugin/tplinksmartbulb",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "checkStatus",
					ip: bulbip
                }),
                contentType: "application/json; charset=UTF-8"
            }).done(function(){
				self.settings.saveData();
				});
        }; 
		
		self.disconnectPrinter = function() {
            $.ajax({
                url: API_BASEURL + "plugin/tplinksmartbulb",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "disconnectPrinter"
                }),
                contentType: "application/json; charset=UTF-8"
            });			
		}
		
		self.connectPrinter = function() {
            $.ajax({
                url: API_BASEURL + "plugin/tplinksmartbulb",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "connectPrinter"
                }),
                contentType: "application/json; charset=UTF-8"
            });			
		}
		
		self.checkStatuses = function() {
			ko.utils.arrayForEach(self.settings.settings.plugins.tplinksmartbulb.arrSmartBulbs(),function(item){
				if(item.ip() !== "") {
					console.log("checking " + item.ip())
					self.checkStatus(item.ip());
				}
			});
			if (self.settings.settings.plugins.tplinksmartbulb.pollingEnabled()) {
				setTimeout(function() {self.checkStatuses();}, (parseInt(self.settings.settings.plugins.tplinksmartbulb.pollingInterval(),10) * 60000));
			};
        };
    }

    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        tplinksmartbulbViewModel,

        // e.g. loginStateViewModel, settingsViewModel, ...
        ["settingsViewModel","loginStateViewModel"],

        // "#navbar_plugin_tplinksmartbulb","#settings_plugin_tplinksmartbulb"
        ["#navbar_plugin_tplinksmartbulb","#settings_plugin_tplinksmartbulb"]
    ]);
});
