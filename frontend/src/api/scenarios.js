import service from './index'

/**
 * List all available scenario presets
 * @returns {Promise}
 */
export function listScenarios() {
  return service({
    url: '/api/scenarios/list',
    method: 'get'
  })
}

/**
 * Get a specific scenario's config
 * @param {String} scenarioId - The scenario directory name
 * @returns {Promise}
 */
export function getScenario(scenarioId) {
  return service({
    url: `/api/scenarios/${scenarioId}`,
    method: 'get'
  })
}

/**
 * Get the download URL for a scenario seed file
 * @param {String} scenarioId - The scenario directory name
 * @param {String} filename - The seed file name
 * @returns {String} The download URL
 */
export function getScenarioFileUrl(scenarioId, filename) {
  return `/api/scenarios/${scenarioId}/file/${filename}`
}

/**
 * Download a scenario seed file as a File object
 * @param {String} scenarioId - The scenario directory name
 * @param {String} filename - The seed file name
 * @returns {Promise<File>}
 */
export async function downloadScenarioFile(scenarioId, filename) {
  const response = await fetch(`/api/scenarios/${scenarioId}/file/${filename}`)
  const blob = await response.blob()
  return new File([blob], filename, { type: 'text/markdown' })
}
