<template>
  <div class="scenario-presets" v-if="scenarios.length > 0">
    <div class="presets-header">
      <span class="preset-icon">⚡</span>
      <span class="presets-label">{{ $t('scenarios.quickStart') }}</span>
      <span class="presets-hint">{{ $t('scenarios.clickToLoad') }}</span>
    </div>
    
    <div class="presets-grid">
      <div 
        v-for="scenario in scenarios" 
        :key="scenario.id"
        class="preset-card"
        :class="{ active: selectedId === scenario.id, loading: loadingId === scenario.id }"
        @click="selectScenario(scenario)"
      >
        <div class="preset-card-icon">{{ scenario.icon || '🔮' }}</div>
        <div class="preset-card-content">
          <div class="preset-card-name">{{ getLocalizedName(scenario) }}</div>
          <div class="preset-card-desc">{{ getLocalizedDesc(scenario) }}</div>
          <div class="preset-card-meta">
            <span class="meta-tag">{{ scenario.seed_files?.length || 0 }} {{ $t('scenarios.seedFiles') }}</span>
            <span v-if="scenario.recommended_rounds" class="meta-tag">~{{ scenario.recommended_rounds }} {{ $t('common.rounds') }}</span>
            <span v-if="scenario.category" class="meta-tag category-tag">{{ scenario.category }}</span>
          </div>
        </div>
        <div class="preset-card-arrow" v-if="loadingId !== scenario.id">→</div>
        <div class="preset-card-spinner" v-else>
          <span class="spinner"></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { listScenarios, downloadScenarioFile } from '../api/scenarios'

const { locale } = useI18n()

const emit = defineEmits(['scenario-loaded'])

const scenarios = ref([])
const selectedId = ref(null)
const loadingId = ref(null)

const getLocalizedName = (scenario) => {
  if (locale.value === 'zh' && scenario.name_zh) return scenario.name_zh
  return scenario.name
}

const getLocalizedDesc = (scenario) => {
  if (locale.value === 'zh' && scenario.description_zh) return scenario.description_zh
  return scenario.description
}

const getLocalizedRequirement = (scenario) => {
  if (locale.value === 'zh' && scenario.simulation_requirement_zh) return scenario.simulation_requirement_zh
  return scenario.simulation_requirement
}

const selectScenario = async (scenario) => {
  if (loadingId.value) return
  
  selectedId.value = scenario.id
  loadingId.value = scenario.id
  
  try {
    // Download all seed files as File objects
    const filePromises = (scenario.seed_files || []).map(filename => 
      downloadScenarioFile(scenario.id, filename)
    )
    const files = await Promise.all(filePromises)
    
    // Emit the loaded scenario data
    emit('scenario-loaded', {
      files,
      simulationRequirement: getLocalizedRequirement(scenario),
      scenarioName: getLocalizedName(scenario)
    })
  } catch (error) {
    console.error('Failed to load scenario:', error)
    selectedId.value = null
  } finally {
    loadingId.value = null
  }
}

onMounted(async () => {
  try {
    const res = await listScenarios()
    if (res?.data?.scenarios) {
      scenarios.value = res.data.scenarios
    }
  } catch (error) {
    console.error('Failed to load scenario presets:', error)
  }
})
</script>

<style scoped>
.scenario-presets {
  margin-bottom: 16px;
}

.presets-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #666;
}

.preset-icon {
  font-size: 0.9rem;
}

.presets-label {
  font-weight: 600;
  color: #333;
}

.presets-hint {
  color: #AAA;
  font-size: 0.7rem;
}

.presets-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preset-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid #E5E5E5;
  background: #FAFAFA;
  cursor: pointer;
  transition: all 0.2s ease;
}

.preset-card:hover {
  border-color: #999;
  background: #F0F0F0;
  transform: translateX(4px);
}

.preset-card.active {
  border-color: #FF4500;
  background: #FFF8F5;
}

.preset-card.loading {
  pointer-events: none;
  opacity: 0.7;
}

.preset-card-icon {
  font-size: 1.5rem;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.preset-card-content {
  flex: 1;
  min-width: 0;
}

.preset-card-name {
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 2px;
  color: #111;
}

.preset-card-desc {
  font-size: 0.75rem;
  color: #888;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.preset-card-meta {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.meta-tag {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  padding: 2px 6px;
  background: #EAEAEA;
  color: #666;
  border-radius: 2px;
}

.category-tag {
  background: #FFF3E0;
  color: #E65100;
  text-transform: capitalize;
}

.preset-card-arrow {
  font-size: 1.1rem;
  color: #CCC;
  flex-shrink: 0;
  transition: color 0.2s;
}

.preset-card:hover .preset-card-arrow {
  color: #FF4500;
}

.preset-card-spinner {
  flex-shrink: 0;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #E5E5E5;
  border-top-color: #FF4500;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
