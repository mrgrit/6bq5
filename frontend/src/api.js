const BASE = ''

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  const ct = res.headers.get('content-type') || ''
  const data = ct.includes('json') ? await res.json() : await res.text()
  if (!res.ok) {
    const msg = typeof data === 'string' ? data : data.detail || JSON.stringify(data)
    throw new Error(`${res.status} ${msg}`)
  }
  return data
}

export const api = {
  health: () => req('/api/health'),

  kg: {
    stats: () => req('/api/kg/stats'),
    nodes: (params = {}) => {
      const q = new URLSearchParams(params).toString()
      return req('/api/kg/nodes' + (q ? '?' + q : ''))
    },
    node: (id) => req('/api/kg/node/' + encodeURIComponent(id)),
    upsertNode: (n) => req('/api/kg/node', { method: 'POST', body: JSON.stringify(n) }),
    deleteNode: (id) => req('/api/kg/node/' + encodeURIComponent(id), { method: 'DELETE' }),
    edges: () => req('/api/kg/edges'),
    addEdge: (e) => req('/api/kg/edge', { method: 'POST', body: JSON.stringify(e) }),
    deleteEdge: (id) => req('/api/kg/edge/' + id, { method: 'DELETE' }),
    search: (q) => req('/api/kg/search?q=' + encodeURIComponent(q)),
    importance: (k = 50) => req('/api/kg/importance?top_k=' + k),
    subgraph: (id, hops = 1) => req('/api/kg/subgraph/' + encodeURIComponent(id) + '?hops=' + hops),
    snapshots: () => req('/api/kg/snapshot'),
    snapshot: (label, description = '') =>
      req('/api/kg/snapshot', { method: 'POST', body: JSON.stringify({ label, description }) }),
    diff: (sid) => req('/api/kg/snapshot/' + sid + '/diff'),
    restore: (sid) => req('/api/kg/snapshot/' + sid + '/restore', { method: 'POST' }),
  },

  poison: {
    recipes: () => req('/api/poison/recipes'),
    run: (recipe, params, experiment_id) =>
      req('/api/poison/run', {
        method: 'POST',
        body: JSON.stringify({ recipe, params, experiment_id }),
      }),
    log: () => req('/api/poison/log'),
    cleanup: () => req('/api/poison/cleanup', { method: 'POST' }),
  },

  defense: {
    rules: () => req('/api/defense/rules'),
    upsert: (r) => req('/api/defense/rules', { method: 'POST', body: JSON.stringify(r) }),
    remove: (id) => req('/api/defense/rules/' + id, { method: 'DELETE' }),
    alerts: () => req('/api/defense/alerts'),
    scanFull: (eid) =>
      req('/api/defense/scan/full' + (eid ? '?experiment_id=' + eid : ''), { method: 'POST' }),
    scanCentrality: (z = 3) =>
      req('/api/defense/scan/centrality?z=' + z, { method: 'POST' }),
    cert: (id) => req('/api/defense/cert/' + encodeURIComponent(id)),
    distribution: (sid) => req('/api/defense/distribution/' + sid),
  },

  pentest: {
    craft: (target_node, recipe_hint = '', use_kg_context = true, experiment_id = null) =>
      req('/api/pentest/craft', {
        method: 'POST',
        body: JSON.stringify({ target_node, recipe_hint, use_kg_context, experiment_id }),
      }),
    exec: (service, command, experiment_id = null) =>
      req('/api/pentest/exec', {
        method: 'POST',
        body: JSON.stringify({ service, command, experiment_id }),
      }),
  },

  experiments: {
    create: (e) => req('/api/experiments', { method: 'POST', body: JSON.stringify(e) }),
    list: (status) => req('/api/experiments' + (status ? '?status=' + status : '')),
    get: (id) => req('/api/experiments/' + id),
    setStatus: (id, status) =>
      req('/api/experiments/' + id + '/status', {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      }),
  },

  notes: {
    list: (eid, tag) => {
      const q = new URLSearchParams()
      if (eid) q.set('experiment_id', eid)
      if (tag) q.set('tag', tag)
      return req('/api/notes' + (q.toString() ? '?' + q.toString() : ''))
    },
    create: (body, tag, experiment_id) =>
      req('/api/notes', {
        method: 'POST',
        body: JSON.stringify({ body, tag, experiment_id }),
      }),
  },

  rag: {
    trace: (query, retrieved_ids, poisoned, experiment_id) =>
      req('/api/rag/trace', {
        method: 'POST',
        body: JSON.stringify({ query, retrieved_ids, poisoned, experiment_id }),
      }),
    list: (eid) => req('/api/rag/trace' + (eid ? '?experiment_id=' + eid : '')),
  },

  memory: {
    record: (m) => req('/api/memory/trace', { method: 'POST', body: JSON.stringify(m) }),
    list: (eid) => req('/api/memory/trace' + (eid ? '?experiment_id=' + eid : '')),
  },

  infra: {
    status: () => req('/api/infra/status'),
    up: (services) => req('/api/infra/up', { method: 'POST', body: JSON.stringify({ services }) }),
    down: () => req('/api/infra/down', { method: 'POST' }),
    restart: (s) => req('/api/infra/restart/' + s, { method: 'POST' }),
    logs: (s, tail = 200) => req('/api/infra/logs/' + s + '?tail=' + tail),
    exec: (s, command) =>
      req('/api/infra/exec/' + s, { method: 'POST', body: JSON.stringify({ command }) }),
    history: () => req('/api/infra/history'),
    sync: () => req('/api/infra/sync', { method: 'POST' }),
  },

  bastion: {
    chat: (message) => req('/api/bastion/chat', { method: 'POST', body: JSON.stringify({ message }) }),
  },

  anchors: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return req('/api/anchors' + (q ? '?' + q : ''))
  },
}
