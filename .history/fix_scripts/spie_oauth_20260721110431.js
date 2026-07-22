(function executeFixScript() {
    const CONFIG = {
        name: 'SPIE MCP Server',
        comments: 'OAuth application registry for the SPIE MCP server connection to ServiceNow.',
        grantType: 'client_credentials',
        redirectUrl: '',
        clientId: '',
        clientSecret: '',
        clientType: 'integration_as_a_service',
        active: true,
        accessTokenLifespanSeconds: 1800,
        refreshTokenLifespanSeconds: 86400
    };

	if (!checkForInboundOauthProp()) {
		gs.error('System property glide.oauth.inbound.client.credential.grant_type.enabled not enabled.');
		return;
	}

    const TABLE_NAME = 'oauth_entity';

    if (!GlideTableDescriptor.isValid(TABLE_NAME)) {
        gs.error('SPIE OAuth fix script failed: table ' + TABLE_NAME + ' was not found on this instance.');
        return;
    }

    var registry = findExistingRegistry(CONFIG.name);
    var isInsert = !registry;

    if (!registry) {
        registry = new GlideRecord(TABLE_NAME);
        registry.initialize();
    }

    var generatedClientId = CONFIG.clientId || generateToken();
    var generatedClientSecret = CONFIG.clientSecret || generateToken() + generateToken();

    assignFirstValid(registry, ['name'], CONFIG.name);
    assignFirstValid(registry, ['comments'], CONFIG.comments);
    assignFirstValid(registry, ['client_id'], generatedClientId);
    assignFirstValid(registry, ['client_secret'], generatedClientSecret);
    assignFirstValid(registry, ['redirect_url', 'redirect_urls'], CONFIG.redirectUrl);
    assignFirstValid(registry, ['grant_type', 'grant_types', 'default_grant_type'], CONFIG.grantType);
    assignFirstValid(registry, ['access_token_lifespan'], String(CONFIG.accessTokenLifespanSeconds));
    assignFirstValid(registry, ['refresh_token_lifespan'], String(CONFIG.refreshTokenLifespanSeconds));
    assignFirstValid(registry, ['client_type'], CONFIG.clientType);
    assignFirstValid(registry, ['active'], CONFIG.active);

    var sysId = isInsert ? registry.insert() : registry.update();
    if (!sysId) {
        gs.error('SPIE OAuth fix script failed: unable to save OAuth application registry ' + CONFIG.name + '.');
        return;
    }

    gs.info('SPIE OAuth application registry ' + (isInsert ? 'created' : 'updated') + '.');
    gs.info('Name: ' + CONFIG.name);
    gs.info('Sys ID: ' + sysId);
    gs.info('Client ID: ' + generatedClientId);
    gs.info('Client Secret: ' + generatedClientSecret);

	function checkForInboundOauthProp() {
		const exists = gs.getProperty('glide.oauth.inbound.client.credential.grant_type.enabled');
		return exists;
	}

    function findExistingRegistry(name) {
        var gr = new GlideRecord(TABLE_NAME);
        gr.addQuery('name', name);
        gr.setLimit(1);
        gr.query();
        if (gr.next()) {
            return gr;
        }
        return null;
    }

    function assignFirstValid(gr, fieldNames, value) {
        if (value === '' || value === null || typeof value === 'undefined') {
            return;
        }

        for (var i = 0; i < fieldNames.length; i += 1) {
            var fieldName = fieldNames[i];
            if (!gr.isValidField(fieldName)) {
                continue;
            }
            gr.setValue(fieldName, value);
            return;
        }
    }

    function generateToken() {
        return gs.generateGUID().replace(/-/g, '');
    }
})();