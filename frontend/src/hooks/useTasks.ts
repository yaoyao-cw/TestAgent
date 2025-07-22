import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'
import type { Task, TaskSubmissionRequest, TaskListResponse } from '@/types'
import toast from 'react-hot-toast'

export function useTasks(params: any = {}) {
  return useQuery<TaskListResponse>({
    queryKey: ['tasks', params],
    queryFn: async () => {
      const response = await apiClient.listTasks(params)
      return response.data
    },
    refetchInterval: 5000, // 每5秒刷新一次
  })
}

export function useTask(taskId: string) {
  return useQuery<Task>({
    queryKey: ['tasks', taskId],
    queryFn: async () => {
      const response = await apiClient.getTaskStatus(taskId)
      return response.data
    },
    enabled: !!taskId,
    refetchInterval: (data) => {
      // 如果任务还在运行，每2秒刷新一次
      if (data?.status === 'running' || data?.status === 'pending') {
        return 2000
      }
      // 已完成的任务不需要频繁刷新
      return false
    },
  })
}

export function useSubmitTask() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: TaskSubmissionRequest) => {
      const response = await apiClient.submitTask(data)
      return response.data
    },
    onSuccess: (data) => {
      toast.success(`任务已提交: ${data.task_id}`)
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
    onError: (error: any) => {
      toast.error(`提交任务失败: ${error.message}`)
    },
  })
}

export function useCancelTask() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (taskId: string) => {
      const response = await apiClient.cancelTask(taskId)
      return response.data
    },
    onSuccess: (data, taskId) => {
      toast.success('任务已取消')
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['tasks', taskId] })
    },
    onError: (error: any) => {
      toast.error(`取消任务失败: ${error.message}`)
    },
  })
}

export function useRetryTask() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (taskId: string) => {
      const response = await apiClient.retryTask(taskId)
      return response.data
    },
    onSuccess: (data) => {
      toast.success(`任务已重试: ${data.task_id}`)
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
    onError: (error: any) => {
      toast.error(`重试任务失败: ${error.message}`)
    },
  })
}

export function useTaskResult(taskId: string, format: string = 'json') {
  return useQuery({
    queryKey: ['tasks', taskId, 'result', format],
    queryFn: async () => {
      const response = await apiClient.getTaskResult(taskId, format)
      return response.data
    },
    enabled: !!taskId,
  })
}