export function sourceKey(source) {
  return JSON.stringify([source.client_code, source.project_code, source.code]);
}

export function sourceScope(source) {
  return source ? {
    client_code: source.client_code,
    project_code: source.project_code,
    source_code: source.code,
  } : {};
}

export function datasetScope(dataset) {
  return {
    client_code: dataset.client,
    project_code: dataset.project,
    source_code: dataset.source_code,
  };
}

export function matchesSource(source, scope) {
  return Object.entries(scope).every(([key, value]) => (
    (key === 'source_code' ? source.code : source[key]) === value
  ));
}
