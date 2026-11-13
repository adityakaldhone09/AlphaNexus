import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Company } from '../types';

interface CompanyState {
  selectedCompany: Company | null;
  activeTab: string;
  setSelectedCompany: (company: Company | null) => void;
  setActiveTab: (tab: string) => void;
}

export const useCompanyStore = create<CompanyState>()(
  persist(
    (set) => ({
      selectedCompany: null,
      activeTab: 'overview',
      setSelectedCompany: (company) => set({ selectedCompany: company }),
      setActiveTab: (tab) => set({ activeTab: tab }),
    }),
    {
      name: 'alphanexus-company-store',
    }
  )
);
