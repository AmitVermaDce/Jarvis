<template>
  <div class="demand-sensing-view">
    <div class="header">
      <h1>{{ t('demandSensing.title') }}</h1>
      <div class="actions">
        <button @click="fetchSummary" class="btn-refresh">
          {{ t('demandSensing.refresh') }}
        </button>
      </div>
    </div>

    <!-- Alerts Section -->
    <div class="section alerts-section" v-if="alerts.length > 0">
      <h2>{{ t('demandSensing.alerts') }}</h2>
      <div class="alerts-list">
        <div
          v-for="alert in alerts"
          :key="alert.id"
          :class="['alert-item', `severity-${alert.severity}`]"
        >
          <div class="alert-header">
            <span :class="['badge', alert.severity]">{{ alert.severity.toUpperCase() }}</span>
            <span class="alert-date">{{ formatDate(alert.created_at) }}</span>
          </div>
          <p class="alert-message">{{ alert.message }}</p>
          <div class="alert-details">
            <span>SKU: {{ alert.sku }}</span>
            <span>Location: {{ alert.location }}</span>
            <span>Deviation: {{ alert.deviation_percent }}%</span>
          </div>
          <button
            v-if="!alert.acknowledged"
            @click="acknowledgeAlert(alert.id)"
            class="btn-acknowledge"
          >
            {{ t('demandSensing.acknowledge') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Forecasts Section -->
    <div class="section forecasts-section">
      <h2>{{ t('demandSensing.forecasts') }}</h2>

      <div class="filters">
        <input
          v-model="filters.sku"
          :placeholder="t('demandSensing.skuPlaceholder')"
          class="input"
        />
        <input
          v-model="filters.location"
          :placeholder="t('demandSensing.locationPlaceholder')"
          class="input"
        />
        <button @click="generateForecast" class="btn-primary">
          {{ t('demandSensing.generateForecast') }}
        </button>
      </div>

      <div v-if="loading" class="loading">{{ t('demandSensing.loading') }}</div>

      <div v-else-if="forecasts.length > 0" class="forecasts-table-wrapper">
        <table class="forecasts-table">
          <thead>
            <tr>
              <th>{{ t('demandSensing.date') }}</th>
              <th>{{ t('demandSensing.sku') }}</th>
              <th>{{ t('demandSensing.location') }}</th>
              <th>{{ t('demandSensing.predictedDemand') }}</th>
              <th>{{ t('demandSensing.confidence') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="forecast in forecasts" :key="`${forecast.sku}-${forecast.location}-${forecast.date}`">
              <td>{{ forecast.date }}</td>
              <td>{{ forecast.sku }}</td>
              <td>{{ forecast.location }}</td>
              <td class="demand-value">{{ forecast.predicted_demand }}</td>
              <td>
                <div class="confidence-bar">
                  <div
                    class="confidence-fill"
                    :style="{ width: `${forecast.confidence * 100}%` }"
                    :class="getConfidenceClass(forecast.confidence)"
                  ></div>
                  <span>{{ (forecast.confidence * 100).toFixed(0) }}%</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="empty-state">
        <p>{{ t('demandSensing.noForecasts') }}</p>
      </div>
    </div>

    <!-- Adjustments Section -->
    <div class="section adjustments-section" v-if="adjustments.length > 0">
      <h2>{{ t('demandSensing.adjustments') }}</h2>
      <div class="adjustments-list">
        <div v-for="adj in adjustments" :key="adj.id" class="adjustment-item">
          <div class="adj-header">
            <span class="adj-sku">{{ adj.sku }} @ {{ adj.location }}</span>
            <span class="adj-date">{{ adj.date }}</span>
          </div>
          <div class="adj-values">
            <span class="old-value">{{ adj.previous_forecast }}</span>
            <span class="arrow">→</span>
            <span class="new-value">{{ adj.new_forecast }}</span>
            <span class="deviation">({{ adj.deviation_percent }}%)</span>
          </div>
          <p class="adj-reason">{{ adj.reason }}</p>
        </div>
      </div>
    </div>

    <!-- Add Observation Form -->
    <div class="section add-observation">
      <h2>{{ t('demandSensing.addObservation') }}</h2>
      <div class="form-row">
        <input v-model="observation.sku" :placeholder="t('demandSensing.sku')" class="input" />
        <input v-model="observation.location" :placeholder="t('demandSensing.location')" class="input" />
        <input v-model="observation.date" type="date" class="input" />
        <input v-model="observation.demand" type="number" :placeholder="t('demandSensing.demand')" class="input" />
        <button @click="addObservation" class="btn-primary">
          {{ t('demandSensing.add') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

const { t } = useI18n()

const props = defineProps({
  projectId: {
    type: String,
    required: true
  }
})

const loading = ref(false)
const alerts = ref([])
const forecasts = ref([])
const adjustments = ref([])

const filters = ref({
  sku: '',
  location: ''
})

const observation = ref({
  sku: '',
  location: '',
  date: new Date().toISOString().split('T')[0],
  demand: ''
})

const API_BASE = '/api/demand-sensing'

const fetchSummary = async () => {
  try {
    loading.value = true
    const response = await axios.get(`${API_BASE}/summary/${props.projectId}`)
    if (response.data.success) {
      alerts.value = response.data.latest_alerts || []
      adjustments.value = response.data.recent_adjustments_list || []
    }
  } catch (error) {
    console.error('Error fetching summary:', error)
  } finally {
    loading.value = false
  }
}

const generateForecast = async () => {
  if (!filters.value.sku || !filters.value.location) {
    alert(t('demandSensing.fillFilters'))
    return
  }

  try {
    loading.value = true
    const response = await axios.post(`${API_BASE}/forecast`, {
      project_id: props.projectId,
      sku: filters.value.sku,
      location: filters.value.location,
      start_date: new Date().toISOString().split('T')[0],
      days: 14
    })

    if (response.data.success) {
      forecasts.value = response.data.forecasts
    }
  } catch (error) {
    console.error('Error generating forecast:', error)
  } finally {
    loading.value = false
  }
}

const acknowledgeAlert = async (alertId) => {
  try {
    await axios.post(`${API_BASE}/alerts/${alertId}/acknowledge?project_id=${props.projectId}`)
    await fetchSummary()
  } catch (error) {
    console.error('Error acknowledging alert:', error)
  }
}

const addObservation = async () => {
  if (!observation.value.sku || !observation.value.location || !observation.value.demand) {
    alert(t('demandSensing.fillAllFields'))
    return
  }

  try {
    await axios.post(`${API_BASE}/observations`, {
      project_id: props.projectId,
      ...observation.value,
      demand: parseFloat(observation.value.demand)
    })

    // Reset and refresh
    observation.value.demand = ''
    await fetchSummary()
    alert(t('demandSensing.observationAdded'))
  } catch (error) {
    console.error('Error adding observation:', error)
  }
}

const formatDate = (dateStr) => {
  return new Date(dateStr).toLocaleString()
}

const getConfidenceClass = (confidence) => {
  if (confidence >= 0.8) return 'high'
  if (confidence >= 0.5) return 'medium'
  return 'low'
}

onMounted(() => {
  fetchSummary()
})
</script>

<style scoped>
.demand-sensing-view {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header h1 {
  font-size: 24px;
  font-weight: 600;
}

.section {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.section h2 {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
}

/* Alerts */
.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alert-item {
  padding: 16px;
  border-radius: 8px;
  border-left: 4px solid;
}

.alert-item.severity-info {
  background: #e3f2fd;
  border-color: #2196f3;
}

.alert-item.severity-warning {
  background: #fff3e0;
  border-color: #ff9800;
}

.alert-item.severity-critical {
  background: #ffebee;
  border-color: #f44336;
}

.alert-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.badge.info { background: #2196f3; color: white; }
.badge.warning { background: #ff9800; color: white; }
.badge.critical { background: #f44336; color: white; }

.alert-date {
  font-size: 12px;
  color: #666;
}

.alert-message {
  margin: 8px 0;
  font-weight: 500;
}

.alert-details {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #666;
}

.btn-acknowledge {
  margin-top: 8px;
  padding: 6px 12px;
  background: #4caf50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

/* Forecasts */
.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.btn-refresh, .btn-primary {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-refresh {
  background: #666;
  color: white;
}

.btn-primary {
  background: #2196f3;
  color: white;
}

.forecasts-table-wrapper {
  overflow-x: auto;
}

.forecasts-table {
  width: 100%;
  border-collapse: collapse;
}

.forecasts-table th,
.forecasts-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.forecasts-table th {
  background: #f5f5f5;
  font-weight: 600;
}

.demand-value {
  font-weight: 600;
  color: #2196f3;
}

.confidence-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.confidence-fill {
  height: 8px;
  border-radius: 4px;
  transition: width 0.3s;
}

.confidence-fill.high { background: #4caf50; }
.confidence-fill.medium { background: #ff9800; }
.confidence-fill.low { background: #f44336; }

.empty-state {
  text-align: center;
  padding: 40px;
  color: #666;
}

.loading {
  text-align: center;
  padding: 20px;
  color: #666;
}

/* Adjustments */
.adjustments-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.adjustment-item {
  padding: 12px;
  background: #f5f5f5;
  border-radius: 4px;
}

.adj-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.adj-sku {
  font-weight: 600;
}

.adj-values {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.old-value {
  text-decoration: line-through;
  color: #666;
}

.arrow {
  color: #2196f3;
  font-weight: bold;
}

.new-value {
  font-weight: 600;
  color: #2196f3;
}

.deviation {
  color: #f44336;
}

.adj-reason {
  font-size: 13px;
  color: #666;
  margin: 0;
}

/* Add Observation */
.form-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.form-row .input {
  flex: 1;
  min-width: 150px;
}
</style>