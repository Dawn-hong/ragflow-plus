import userService from '@/services/user-service';
import { useQuery } from '@tanstack/react-query';

interface MinerUConfig {
  online_enabled: boolean;
}

interface SystemConfig {
  registerEnabled?: number;
  mineru?: MinerUConfig;
}

/**
 * Hook to fetch MinerU configuration status
 * @returns MinerU configuration with loading status
 */
export const useMinerUStatus = () => {
  const { data, isLoading } = useQuery({
    queryKey: ['systemConfig'],
    queryFn: async () => {
      const { data = {} } = await userService.getSystemConfig();
      return (data.data || {}) as SystemConfig;
    },
  });

  return {
    isOnlineMode: data?.mineru?.online_enabled || false,
    loading: isLoading,
  };
};
