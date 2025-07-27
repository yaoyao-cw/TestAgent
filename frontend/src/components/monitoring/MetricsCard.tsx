import React from 'react'
import { 
  TrendingUp, 
  TrendingDown, 
  Minus,
  Activity,
  Clock,
  Zap,
  AlertTriangle,
  CheckCircle
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface MetricsCardProps {
  title: string
  value: string | number
  unit?: string
  change?: number
  changeType?: 'increase' | 'decrease' | 'neutral'
  icon?: React.ReactNode
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'gray'
  className?: string
}

export function MetricsCard({
  title,
  value,
  unit,
  change,
  changeType = 'neutral',
  icon,
  color = 'blue',
  className
}: MetricsCardProps) {
  const getColorClasses = (color: string) => {
    switch (color) {
      case 'green':
        return {
          bg: 'bg-green-50',
          icon: 'text-green-600',
          border: 'border-green-200'
        }
      case 'yellow':
        return {
          bg: 'bg-yellow-50',
          icon: 'text-yellow-600',
          border: 'border-yellow-200'
        }
      case 'red':
        return {
          bg: 'bg-red-50',
          icon: 'text-red-600',
          border: 'border-red-200'
        }
      case 'purple':
        return {
          bg: 'bg-purple-50',
          icon: 'text-purple-600',
          border: 'border-purple-200'
        }
      case 'gray':
        return {
          bg: 'bg-gray-50',
          icon: 'text-gray-600',
          border: 'border-gray-200'
        }
      default: // blue
        return {
          bg: 'bg-blue-50',
          icon: 'text-blue-600',
          border: 'border-blue-200'
        }
    }
  }

  const getChangeIcon = () => {
    switch (changeType) {
      case 'increase':
        return <TrendingUp className="w-3 h-3 text-green-600" />
      case 'decrease':
        return <TrendingDown className="w-3 h-3 text-red-600" />
      default:
        return <Minus className="w-3 h-3 text-gray-400" />
    }
  }

  const getChangeColor = () => {
    switch (changeType) {
      case 'increase':
        return 'text-green-600'
      case 'decrease':
        return 'text-red-600'
      default:
        return 'text-gray-500'
    }
  }

  const colorClasses = getColorClasses(color)

  return (
    <div className={cn(
      "bg-white border rounded-lg p-4 hover:shadow-md transition-shadow",
      colorClasses.border,
      className
    )}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            {icon && (
              <div className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center",
                colorClasses.bg
              )}>
                <div className={colorClasses.icon}>
                  {icon}
                </div>
              </div>
            )}
            <h3 className="text-sm font-medium text-gray-600">{title}</h3>
          </div>
          
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-gray-900">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </span>
            {unit && (
              <span className="text-sm text-gray-500">{unit}</span>
            )}
          </div>

          {change !== undefined && (
            <div className="flex items-center space-x-1 mt-2">
              {getChangeIcon()}
              <span className={cn("text-xs font-medium", getChangeColor())}>
                {Math.abs(change)}%
              </span>
              <span className="text-xs text-gray-500">vs 上期</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// 预定义的指标卡片组件
export function KVCacheHitRateCard({ value, change }: { value: number; change?: number }) {
  return (
    <MetricsCard
      title="KV缓存命中率"
      value={value.toFixed(1)}
      unit="%"
      change={change}
      changeType={change && change > 0 ? 'increase' : change && change < 0 ? 'decrease' : 'neutral'}
      icon={<Zap className="w-4 h-4" />}
      color="green"
    />
  )
}

export function ResponseTimeCard({ value, change }: { value: number; change?: number }) {
  return (
    <MetricsCard
      title="平均响应时间"
      value={value.toFixed(0)}
      unit="ms"
      change={change}
      changeType={change && change > 0 ? 'decrease' : change && change < 0 ? 'increase' : 'neutral'}
      icon={<Clock className="w-4 h-4" />}
      color="blue"
    />
  )
}

export function ErrorRateCard({ value, change }: { value: number; change?: number }) {
  const color = value > 5 ? 'red' : value > 2 ? 'yellow' : 'green'
  
  return (
    <MetricsCard
      title="错误率"
      value={value.toFixed(2)}
      unit="%"
      change={change}
      changeType={change && change > 0 ? 'decrease' : change && change < 0 ? 'increase' : 'neutral'}
      icon={value > 5 ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
      color={color}
    />
  )
}

export function ActiveConnectionsCard({ value, change }: { value: number; change?: number }) {
  return (
    <MetricsCard
      title="活跃连接数"
      value={value}
      change={change}
      changeType={change && change > 0 ? 'increase' : change && change < 0 ? 'decrease' : 'neutral'}
      icon={<Activity className="w-4 h-4" />}
      color="purple"
    />
  )
}