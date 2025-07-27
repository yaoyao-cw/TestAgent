import React, { useState, useEffect, useRef } from 'react'
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts'
import { cn, formatDate } from '@/lib/utils'

interface DataPoint {
  timestamp: string
  value: number
  label?: string
}

interface RealtimeChartProps {
  data: DataPoint[]
  title: string
  color?: string
  type?: 'line' | 'area'
  unit?: string
  maxDataPoints?: number
  height?: number
  className?: string
}

export function RealtimeChart({
  data,
  title,
  color = '#3B82F6',
  type = 'line',
  unit = '',
  maxDataPoints = 50,
  height = 200,
  className
}: RealtimeChartProps) {
  const [chartData, setChartData] = useState<DataPoint[]>([])
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    // 限制数据点数量，保持图表性能
    const limitedData = data.slice(-maxDataPoints)
    setChartData(limitedData)
  }, [data, maxDataPoints])

  const formatTooltipValue = (value: number) => {
    return `${value.toFixed(2)}${unit}`
  }

  const formatXAxisLabel = (timestamp: string) => {
    return formatDate(timestamp, 'HH:mm:ss')
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3">
          <p className="text-sm font-medium text-gray-900">
            {formatDate(label, 'yyyy-MM-dd HH:mm:ss')}
          </p>
          <p className="text-sm text-gray-600">
            <span className="font-medium" style={{ color }}>
              {title}: {formatTooltipValue(payload[0].value)}
            </span>
          </p>
        </div>
      )
    }
    return null
  }

  const renderChart = () => {
    const commonProps = {
      data: chartData,
      margin: { top: 5, right: 30, left: 20, bottom: 5 }
    }

    if (type === 'area') {
      return (
        <AreaChart {...commonProps}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis 
            dataKey="timestamp" 
            tickFormatter={formatXAxisLabel}
            stroke="#6b7280"
            fontSize={12}
          />
          <YAxis 
            stroke="#6b7280"
            fontSize={12}
            tickFormatter={(value) => `${value}${unit}`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            fill={color}
            fillOpacity={0.1}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: color }}
          />
        </AreaChart>
      )
    }

    return (
      <LineChart {...commonProps}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis 
          dataKey="timestamp" 
          tickFormatter={formatXAxisLabel}
          stroke="#6b7280"
          fontSize={12}
        />
        <YAxis 
          stroke="#6b7280"
          fontSize={12}
          tickFormatter={(value) => `${value}${unit}`}
        />
        <Tooltip content={<CustomTooltip />} />
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: color }}
        />
      </LineChart>
    )
  }

  return (
    <div className={cn("bg-white border border-gray-200 rounded-lg p-4", className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-900">{title}</h3>
        <div className="flex items-center space-x-2">
          <div 
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: color }}
          />
          <span className="text-xs text-gray-500">实时数据</span>
        </div>
      </div>
      
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// 预定义的图表组件
export function KVCacheChart({ data }: { data: DataPoint[] }) {
  return (
    <RealtimeChart
      data={data}
      title="KV缓存命中率"
      color="#10B981"
      type="area"
      unit="%"
      height={180}
    />
  )
}

export function ResponseTimeChart({ data }: { data: DataPoint[] }) {
  return (
    <RealtimeChart
      data={data}
      title="响应时间"
      color="#3B82F6"
      type="line"
      unit="ms"
      height={180}
    />
  )
}

export function ErrorRateChart({ data }: { data: DataPoint[] }) {
  return (
    <RealtimeChart
      data={data}
      title="错误率"
      color="#EF4444"
      type="area"
      unit="%"
      height={180}
    />
  )
}

export function MemoryUsageChart({ data }: { data: DataPoint[] }) {
  return (
    <RealtimeChart
      data={data}
      title="内存使用率"
      color="#8B5CF6"
      type="area"
      unit="%"
      height={180}
    />
  )
}