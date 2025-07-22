import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'
import type { SystemStatus } from '@/types'

export function useSystemStatus() {
  return useQuery<SystemStatus>({
    queryKey: ['system', 'status'],
    queryFn: async () => {
      const response = await apiClient.systemStatus()
      return response.data
    },
    refetchInterval: 30000, // 每30秒刷新一次
    retry: 2,
  })
}

export function useSystemMetrics(hours: number = 24) {
  return useQuery({
    queryKey: ['system', 'metrics', hours],
    queryFn: async () => {
      const response = await apiClient.systemMetrics(hours)
      return response.data
    },
    refetchInterval: 60000, // 每分钟刷新一次
  })
}