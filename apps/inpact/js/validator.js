// CycleBoard Data Validator Module
// Handles validation and migration of data

class DataValidator {
  static validateTask(task) {
    const errors = [];

    if (!task.letter || task.letter.length !== 1) {
      errors.push('Task must have a single letter');
    }

    if (!task.task || task.task.trim().length < 2) {
      errors.push('Task description must be at least 2 characters');
    }

    if (task.task && task.task.length > 500) {
      errors.push('Task description too long (max 500 characters)');
    }

    if (task.notes && task.notes.length > 2000) {
      errors.push('Notes too long (max 2000 characters)');
    }

    const validStatuses = [TASK_STATUS.NOT_STARTED, TASK_STATUS.IN_PROGRESS, TASK_STATUS.COMPLETED];
    if (!validStatuses.includes(task.status)) {
      errors.push('Invalid task status');
    }

    return errors;
  }

  static validateDayPlan(plan) {
    const errors = [];

    if (!plan.date || !/^\d{4}-\d{2}-\d{2}$/.test(plan.date)) {
      errors.push('Invalid date format (use YYYY-MM-DD)');
    }

    const validDayTypes = [DAY_TYPE.A, DAY_TYPE.B, DAY_TYPE.C];
    if (!validDayTypes.includes(plan.day_type)) {
      errors.push('Invalid day type (must be A, B, or C)');
    }

    if (plan.rating && (plan.rating < 0 || plan.rating > 5)) {
      errors.push('Rating must be between 0 and 5');
    }

    return errors;
  }

  static validateRoutineStep(step) {
    const errors = [];

    if (!step || step.trim().length === 0) {
      errors.push('Routine step cannot be empty');
    }

    if (step && step.length > 200) {
      errors.push('Routine step too long (max 200 characters)');
    }

    return errors;
  }

  static validateImportData(data) {
    const errors = [];

    if (!data || typeof data !== 'object') {
      errors.push('Invalid data format');
      return errors;
    }

    // Required core fields (must exist for valid backup)
    if (!data.version) {
      errors.push('Data version missing');
    }

    if (!data.AZTask || !Array.isArray(data.AZTask)) {
      errors.push('Invalid or missing AZTask array');
    }

    if (!data.DayPlans || typeof data.DayPlans !== 'object') {
      errors.push('Invalid or missing DayPlans');
    }

    if (!data.Routine || typeof data.Routine !== 'object') {
      errors.push('Invalid or missing Routine');
    }

    // Validate AZTask items structure
    if (data.AZTask && Array.isArray(data.AZTask)) {
      data.AZTask.forEach((task, idx) => {
        if (!task.id || !task.letter || !task.task) {
          errors.push(`AZTask[${idx}] missing required fields (id, letter, task)`);
        }
      });
    }

    // Validate FocusArea if present
    if (data.FocusArea && !Array.isArray(data.FocusArea)) {
      errors.push('FocusArea must be an array');
    }

    // Validate DayTypeTemplates structure if present
    if (data.DayTypeTemplates && typeof data.DayTypeTemplates === 'object') {
      ['A', 'B', 'C'].forEach(type => {
        if (data.DayTypeTemplates[type]) {
          const template = data.DayTypeTemplates[type];
          if (template.timeBlocks && !Array.isArray(template.timeBlocks)) {
            errors.push(`DayTypeTemplates.${type}.timeBlocks must be an array`);
          }
          if (template.routines && !Array.isArray(template.routines)) {
            errors.push(`DayTypeTemplates.${type}.routines must be an array`);
          }
        }
      });
    }

    // Validate Settings structure if present
    if (data.Settings && typeof data.Settings !== 'object') {
      errors.push('Settings must be an object');
    }

    // Validate Journal if present
    if (data.Journal && !Array.isArray(data.Journal)) {
      errors.push('Journal must be an array');
    }

    // Validate MomentumWins if present
    if (data.MomentumWins && !Array.isArray(data.MomentumWins)) {
      errors.push('MomentumWins must be an array');
    }

    // Validate Reflections structure if present
    if (data.Reflections && typeof data.Reflections === 'object') {
      ['weekly', 'monthly', 'quarterly', 'yearly'].forEach(period => {
        if (data.Reflections[period] && !Array.isArray(data.Reflections[period])) {
          errors.push(`Reflections.${period} must be an array`);
        }
      });
    }

    return errors;
  }

  static migrateImportData(imported, defaultState) {
    // Deep merge imported data with defaults to fill missing features
    const migrated = { ...imported };

    // Track what was migrated for user feedback
    const migratedFeatures = [];

    // Ensure all top-level features exist
    const featureDefaults = {
      FocusArea: { check: Array.isArray, default: defaultState.FocusArea },
      DayTypeTemplates: { check: (v) => v && typeof v === 'object', default: defaultState.DayTypeTemplates },
      Settings: { check: (v) => v && typeof v === 'object', default: defaultState.Settings },
      History: { check: (v) => v && typeof v === 'object', default: defaultState.History },
      Journal: { check: Array.isArray, default: defaultState.Journal },
      EightSteps: { check: (v) => v && typeof v === 'object', default: defaultState.EightSteps },
      Contingencies: { check: (v) => v && typeof v === 'object', default: defaultState.Contingencies },
      Reflections: { check: (v) => v && typeof v === 'object', default: defaultState.Reflections },
      MomentumWins: { check: Array.isArray, default: defaultState.MomentumWins }
    };

    for (const [feature, config] of Object.entries(featureDefaults)) {
      if (!migrated[feature] || !config.check(migrated[feature])) {
        migrated[feature] = config.default;
        migratedFeatures.push(feature);
      }
    }

    // Merge Settings (preserve user settings, add missing ones)
    if (imported.Settings && typeof imported.Settings === 'object') {
      migrated.Settings = { ...defaultState.Settings, ...imported.Settings };
    }

    // Merge History (preserve user history, add missing fields)
    if (imported.History && typeof imported.History === 'object') {
      migrated.History = {
        completedTasks: imported.History.completedTasks || [],
        productivityScore: imported.History.productivityScore || 0,
        streak: imported.History.streak || 0,
        timeline: imported.History.timeline || []
      };
    }

    // Merge Reflections (preserve existing, add missing periods)
    if (imported.Reflections && typeof imported.Reflections === 'object') {
      migrated.Reflections = {
        weekly: imported.Reflections.weekly || [],
        monthly: imported.Reflections.monthly || [],
        quarterly: imported.Reflections.quarterly || [],
        yearly: imported.Reflections.yearly || []
      };
    }

    // Merge Contingencies (preserve existing, add missing types)
    if (imported.Contingencies && typeof imported.Contingencies === 'object') {
      migrated.Contingencies = { ...defaultState.Contingencies, ...imported.Contingencies };
    }

    // Ensure DayTypeTemplates has all types (A, B, C)
    if (migrated.DayTypeTemplates) {
      ['A', 'B', 'C'].forEach(type => {
        if (!migrated.DayTypeTemplates[type]) {
          migrated.DayTypeTemplates[type] = defaultState.DayTypeTemplates[type];
          if (!migratedFeatures.includes('DayTypeTemplates')) {
            migratedFeatures.push(`DayTypeTemplates.${type}`);
          }
        }
      });
    }

    // Update version to current
    migrated.version = defaultState.version;

    return { migrated, migratedFeatures };
  }
}

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = DataValidator;
}
