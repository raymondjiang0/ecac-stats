import axios from 'axios'
import type {
  Player, Game, GameCreate, TeamGameStats,
  PlayerGameStats, PlayerAggStats, TeamAggStats,
  IngestPreview, IngestRun,
} from '../types'

const api = axios.create({ baseURL: '/api' })

// Players
export const getPlayers = () => api.get<Player[]>('/players').then(r => r.data)
export const createPlayer = (data: Omit<Player, 'id'>) => api.post<Player>('/players', data).then(r => r.data)
export const updatePlayer = (id: number, data: Partial<Player>) => api.put<Player>(`/players/${id}`, data).then(r => r.data)
export const deletePlayer = (id: number) => api.delete(`/players/${id}`)

// Games
export const getGames = () => api.get<Game[]>('/games').then(r => r.data)
export const createGame = (data: GameCreate) => api.post<Game>('/games', data).then(r => r.data)
export const getGame = (id: number) => api.get<Game>(`/games/${id}`).then(r => r.data)
export const updateGame = (id: number, data: Partial<Game>) => api.put<Game>(`/games/${id}`, data).then(r => r.data)
export const deleteGame = (id: number) => api.delete(`/games/${id}`)

// Team stats
export const getTeamStats = (gameId: number) =>
  api.get<TeamGameStats>(`/games/${gameId}/team-stats`).then(r => r.data).catch(() => null)
export const saveTeamStats = (gameId: number, data: Partial<TeamGameStats>) =>
  api.post<TeamGameStats>(`/games/${gameId}/team-stats`, data).then(r => r.data)

// Player game stats
export const getAllPlayerStats = (gameId: number) =>
  api.get<PlayerGameStats[]>(`/games/${gameId}/players`).then(r => r.data)
export const getPlayerGameStats = (gameId: number, playerId: number) =>
  api.get<PlayerGameStats>(`/games/${gameId}/players/${playerId}`).then(r => r.data).catch(() => null)
export const savePlayerGameStats = (gameId: number, playerId: number, data: Partial<PlayerGameStats>) =>
  api.post<PlayerGameStats>(`/games/${gameId}/players/${playerId}`, data).then(r => r.data)

// Date range params helper
function dateParams(dateFrom?: string, dateTo?: string) {
  const p: Record<string, string> = {}
  if (dateFrom) p.date_from = dateFrom
  if (dateTo) p.date_to = dateTo
  return p
}

// Aggregated stats
export const getTeamAggStats = (dateFrom?: string, dateTo?: string) =>
  api.get<TeamAggStats>('/stats/team', { params: dateParams(dateFrom, dateTo) }).then(r => r.data)
export const getPlayerAggStats = (playerId: number, dateFrom?: string, dateTo?: string) =>
  api.get<PlayerAggStats>(`/stats/player/${playerId}`, { params: dateParams(dateFrom, dateTo) }).then(r => r.data)
export const getAllPlayerAggStats = (dateFrom?: string, dateTo?: string) =>
  api.get<PlayerAggStats[]>('/stats/players/all', { params: dateParams(dateFrom, dateTo) }).then(r => r.data)

// Reports (download PDF)
export const downloadPlayerReport = (playerId: number, playerName: string, dateFrom?: string, dateTo?: string) =>
  api.get(`/reports/player/${playerId}`, { responseType: 'blob', params: dateParams(dateFrom, dateTo) }).then(r => {
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    const suffix = dateFrom || dateTo ? `_${dateFrom ?? ''}_to_${dateTo ?? ''}` : ''
    a.download = `player_${playerName.replace(/ /g, '_')}${suffix}_report.pdf`
    a.click()
    URL.revokeObjectURL(url)
  })

export const downloadTeamReport = (dateFrom?: string, dateTo?: string) =>
  api.get('/reports/team', { responseType: 'blob', params: dateParams(dateFrom, dateTo) }).then(r => {
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    const suffix = dateFrom || dateTo ? `_${dateFrom ?? ''}_to_${dateTo ?? ''}` : ''
    a.download = `team${suffix}_report.pdf`
    a.click()
    URL.revokeObjectURL(url)
  })

export const exportAllData = () =>
  api.get('/stats/export', { responseType: 'blob' }).then(r => {
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    const today = new Date().toISOString().slice(0, 10)
    a.download = `ecac_export_${today}.json`
    a.click()
    URL.revokeObjectURL(url)
  })

// Ingest
export const uploadIngest = (file: File, gameId: number) => {
  const form = new FormData()
  form.append('file', file)
  form.append('game_id', String(gameId))
  return api.post<{
    ingest_run_id: number
    warnings: string[]
    preview: IngestPreview
  }>('/ingest/upload', form).then(r => r.data)
}

export const getIngestRun = (id: number) =>
  api.get<IngestRun>(`/ingest/${id}`).then(r => r.data)
