// Vercel serverless function — POST /api/hubspot/contact
// Required env var: HUBSPOT_TOKEN (HubSpot Private App token, contacts read+write scope)
module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const token = process.env.HUBSPOT_TOKEN;
  if (!token) {
    console.error('HUBSPOT_TOKEN env var not set');
    return res.status(500).json({ error: 'HubSpot not configured' });
  }

  const { email, firstName = '', lastName = '', company = '', website = '', utm = {} } = req.body || {};

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Valid email required' });
  }

  const qualifiedStatus = utm.altusflow_lead_qualified_status ||
    (Number(utm.altusflow_ai_chat_score) >= 7 ? 'AI-Qualified' : 'Form Submitted');

  const properties = {
    email,
    firstname: firstName,
    lastname: lastName,
    // company field from form is the website URL — map to website property
    website: website || company,
    altusflow_lead_source_vertical: utm.altusflow_vertical || utm.altusflow_lead_source_vertical || '',
    altusflow_client_portal_id: utm.altusflow_client_id || 'ALT00',
    altusflow_lead_qualified_status: qualifiedStatus,
    altusflow_first_touch_campaign: utm.altusflow_first_touch_campaign || 'Website Form',
    ...(utm.altusflow_ai_chat_score !== undefined && {
      altusflow_ai_chat_score: String(utm.altusflow_ai_chat_score),
    }),
    ...(utm.altusflow_outbound_trigger_phrase && {
      altusflow_outbound_trigger_phrase: utm.altusflow_outbound_trigger_phrase,
    }),
  };

  try {
    const hsRes = await fetch('https://api.hubapi.com/crm/v3/objects/contacts/batch/upsert', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        inputs: [{ idProperty: 'email', id: email, properties }],
      }),
    });

    if (!hsRes.ok) {
      const body = await hsRes.text();
      console.error('HubSpot API error:', hsRes.status, body);
      return res.status(502).json({ error: 'HubSpot API error' });
    }

    const result = await hsRes.json();
    const contactId = result?.results?.[0]?.id;
    console.log('HubSpot contact upserted:', email, contactId);

    return res.status(200).json({ ok: true, contactId });
  } catch (err) {
    console.error('Contact handler error:', err);
    return res.status(500).json({ error: 'Internal error' });
  }
};
