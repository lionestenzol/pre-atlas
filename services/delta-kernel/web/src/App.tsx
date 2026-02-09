import { useState, useEffect, useCallback } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001/api'

type Mode = 'RECOVER' | 'CLOSE_LOOPS' | 'BUILD' | 'COMPOUND' | 'SCALE'
type TaskStatus = 'OPEN' | 'IN_PROGRESS' | 'DONE' | 'ARCHIVED'

interface Task {
  id: string
  title: string
  status: TaskStatus
  priority: 'HIGH' | 'NORMAL' | 'LOW'
  createdAt: number
}

interface SystemState {
  mode: Mode
  sleepHours: number
  openLoops: number
  leverageBalance: number
  streakDays: number
}

const MODE_COLORS: Record<Mode, string> = {
  RECOVER: '#dc2626',
  CLOSE_LOOPS: '#ca8a04',
  BUILD: '#16a34a',
  COMPOUND: '#2563eb',
  SCALE: '#9333ea',
}

const MODE_DESCRIPTIONS: Record<Mode, string> = {
  RECOVER: 'Rest and restore. Only recovery actions available.',
  CLOSE_LOOPS: 'Clear pending items. Reduce mental load.',
  BUILD: 'Create new work. Full capabilities enabled.',
  COMPOUND: 'Extend and improve existing work.',
  SCALE: 'Delegate, automate, multiply impact.',
}

function App() {
  const [state, setState] = useState<SystemState>({
    mode: 'RECOVER',
    sleepHours: 6,
    openLoops: 0,
    leverageBalance: 0,
    streakDays: 0,
  })

  const [tasks, setTasks] = useState<Task[]>([])
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [showNewTask, setShowNewTask] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [apiConnected, setApiConnected] = useState(false)

  // Load from API
  const loadData = useCallback(async () => {
    try {
      const [stateRes, tasksRes] = await Promise.all([
        fetch(`${API_URL}/state`),
        fetch(`${API_URL}/tasks`),
      ])

      if (stateRes.ok && tasksRes.ok) {
        const stateData = await stateRes.json()
        const tasksData = await tasksRes.json()

        setState(stateData)
        setTasks(tasksData.filter((t: Task) => t.status !== 'ARCHIVED'))
        setApiConnected(true)
      }
    } catch (err) {
      console.log('API not available, using localStorage')
      setApiConnected(false)

      // Fallback to localStorage
      const saved = localStorage.getItem('delta-fabric-state')
      if (saved) {
        const data = JSON.parse(saved)
        setState(data.state)
        setTasks(data.tasks || [])
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Save to API or localStorage
  const saveState = useCallback(async (newState: SystemState) => {
    if (apiConnected) {
      try {
        await fetch(`${API_URL}/state`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newState),
        })
      } catch (err) {
        console.log('Failed to save to API')
      }
    }
    // Always save to localStorage as backup
    localStorage.setItem('delta-fabric-state', JSON.stringify({ state: newState, tasks }))
  }, [apiConnected, tasks])

  // Update open loops count
  useEffect(() => {
    const openCount = tasks.filter(t => t.status !== 'DONE' && t.status !== 'ARCHIVED').length
    if (openCount !== state.openLoops) {
      const newState = { ...state, openLoops: openCount }
      setState(newState)
      saveState(newState)
    }
  }, [tasks])

  const checkModeTransition = (newState: SystemState): Mode => {
    const { mode, sleepHours, openLoops, leverageBalance, streakDays } = newState

    if (sleepHours < 5) return 'RECOVER'
    if (sleepHours < 7 && ['BUILD', 'COMPOUND', 'SCALE'].includes(mode)) return 'CLOSE_LOOPS'

    if (sleepHours >= 7) {
      if (mode === 'RECOVER') return 'CLOSE_LOOPS'
      if (mode === 'CLOSE_LOOPS' && openLoops <= 3) return 'BUILD'
      if (mode === 'BUILD' && leverageBalance >= 5) return 'COMPOUND'
      if (mode === 'COMPOUND' && leverageBalance >= 10 && streakDays >= 3) return 'SCALE'
    }

    if (openLoops > 7 && ['BUILD', 'COMPOUND', 'SCALE'].includes(mode)) return 'CLOSE_LOOPS'

    return mode
  }

  const updateState = async (updates: Partial<SystemState>) => {
    const newState = { ...state, ...updates }
    const newMode = checkModeTransition(newState)
    if (newMode !== newState.mode) {
      setStatusMessage(`Mode: ${newState.mode} → ${newMode}`)
      newState.mode = newMode
    }
    setState(newState)
    await saveState(newState)
  }

  const createTask = async () => {
    if (!newTaskTitle.trim()) return

    if (apiConnected) {
      try {
        const res = await fetch(`${API_URL}/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: newTaskTitle.trim() }),
        })
        const task = await res.json()
        setTasks(t => [...t, task])
      } catch (err) {
        console.log('Failed to create task via API')
      }
    } else {
      const task: Task = {
        id: crypto.randomUUID(),
        title: newTaskTitle.trim(),
        status: 'OPEN',
        priority: 'NORMAL',
        createdAt: Date.now(),
      }
      setTasks(t => [...t, task])
    }

    setNewTaskTitle('')
    setShowNewTask(false)
    setStatusMessage(`Created: ${newTaskTitle.trim()}`)
  }

  const startTask = async (id: string) => {
    if (apiConnected) {
      try {
        await fetch(`${API_URL}/tasks/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'IN_PROGRESS' }),
        })
      } catch (err) {
        console.log('Failed to update task')
      }
    }

    setTasks(t => t.map(task =>
      task.id === id ? { ...task, status: 'IN_PROGRESS' as TaskStatus } : task
    ))
    const task = tasks.find(t => t.id === id)
    setStatusMessage(`Started: ${task?.title}`)
  }

  const completeTask = async (id: string) => {
    if (apiConnected) {
      try {
        await fetch(`${API_URL}/tasks/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'DONE' }),
        })
      } catch (err) {
        console.log('Failed to update task')
      }
    }

    setTasks(t => t.map(task =>
      task.id === id ? { ...task, status: 'DONE' as TaskStatus } : task
    ))
    const task = tasks.find(t => t.id === id)
    await updateState({ leverageBalance: state.leverageBalance + 1 })
    setStatusMessage(`Completed: ${task?.title}`)
  }

  const deleteTask = async (id: string) => {
    if (apiConnected) {
      try {
        await fetch(`${API_URL}/tasks/${id}`, { method: 'DELETE' })
      } catch (err) {
        console.log('Failed to delete task')
      }
    }
    setTasks(t => t.filter(task => task.id !== id))
  }

  const signalSleep = (hours: number) => {
    updateState({ sleepHours: hours })
    setStatusMessage(hours >= 7 ? 'Recorded: Good sleep' : 'Recorded: Poor sleep')
  }

  const signalBigWin = () => {
    updateState({
      leverageBalance: state.leverageBalance + 2,
      streakDays: state.streakDays + 1
    })
    setStatusMessage('Big win! Leverage +2, Streak +1')
  }

  const openTasks = tasks.filter(t => t.status !== 'DONE' && t.status !== 'ARCHIVED')
  const canStartTasks = ['BUILD', 'COMPOUND', 'SCALE'].includes(state.mode)

  if (loading) {
    return <div className="app loading">Loading...</div>
  }

  return (
    <div className="app">
      {/* Connection Status */}
      <div className={`connection-status ${apiConnected ? 'connected' : 'local'}`}>
        {apiConnected ? '● Synced' : '○ Local only'}
      </div>

      {/* Header */}
      <header className="header" style={{ backgroundColor: MODE_COLORS[state.mode] }}>
        <h1>MODE: {state.mode}</h1>
        <p>{MODE_DESCRIPTIONS[state.mode]}</p>
      </header>

      {/* Signals */}
      <section className="signals">
        <h2>Signals</h2>
        <div className="signal-grid">
          <div className={`signal ${state.sleepHours >= 7 ? 'good' : state.sleepHours >= 5 ? 'warn' : 'bad'}`}>
            <span className="label">Sleep</span>
            <span className="value">{state.sleepHours}h</span>
          </div>
          <div className={`signal ${state.openLoops <= 3 ? 'good' : state.openLoops <= 7 ? 'warn' : 'bad'}`}>
            <span className="label">Open Loops</span>
            <span className="value">{state.openLoops}</span>
          </div>
          <div className="signal">
            <span className="label">Leverage</span>
            <span className="value">{state.leverageBalance}</span>
          </div>
          <div className="signal">
            <span className="label">Streak</span>
            <span className="value">{state.streakDays}d</span>
          </div>
        </div>

        <div className="signal-actions">
          <button onClick={() => signalSleep(8)}>Slept Well (8h)</button>
          <button onClick={() => signalSleep(4)}>Slept Poorly (4h)</button>
          <button onClick={signalBigWin}>Big Win!</button>
        </div>
      </section>

      {/* Tasks */}
      <section className="tasks">
        <div className="section-header">
          <h2>Tasks ({openTasks.length} open)</h2>
          <button className="primary" onClick={() => setShowNewTask(true)}>+ New Task</button>
        </div>

        {showNewTask && (
          <div className="new-task-form">
            <input
              type="text"
              placeholder="Task title..."
              value={newTaskTitle}
              onChange={e => setNewTaskTitle(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && createTask()}
              autoFocus
            />
            <button onClick={createTask}>Create</button>
            <button onClick={() => setShowNewTask(false)}>Cancel</button>
          </div>
        )}

        {openTasks.length === 0 ? (
          <p className="empty">No open tasks. Press "+ New Task" to create one.</p>
        ) : (
          <ul className="task-list">
            {openTasks.map(task => (
              <li key={task.id} className={`task ${task.status.toLowerCase()}`}>
                <div className="task-info">
                  <span className={`status-icon ${task.status.toLowerCase()}`}>
                    {task.status === 'IN_PROGRESS' ? '►' : '○'}
                  </span>
                  <span className="title">{task.title}</span>
                </div>
                <div className="task-actions">
                  {task.status === 'OPEN' && canStartTasks && (
                    <button onClick={() => startTask(task.id)}>Start</button>
                  )}
                  {task.status === 'IN_PROGRESS' && (
                    <button className="complete" onClick={() => completeTask(task.id)}>Complete</button>
                  )}
                  <button className="delete" onClick={() => deleteTask(task.id)}>×</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Status */}
      {statusMessage && (
        <div className="status-bar">
          {statusMessage}
        </div>
      )}

      {/* Mode Hint */}
      {state.mode === 'RECOVER' && (
        <div className="hint">
          Signal "Slept Well" to exit RECOVER mode
        </div>
      )}
      {state.mode === 'CLOSE_LOOPS' && state.openLoops > 3 && (
        <div className="hint">
          Complete tasks to reduce loops below 4 and unlock BUILD mode
        </div>
      )}
    </div>
  )
}

export default App
