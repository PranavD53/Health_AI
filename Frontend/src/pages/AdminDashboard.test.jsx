import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import AdminDashboard from './AdminDashboard';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';

// Mock dependencies
vi.mock('../services/api', () => ({
  api: {
    getAdminDashboard: vi.fn(),
    getComplaints: vi.fn(),
  },
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('../context/LanguageContext', () => ({
  useLanguage: vi.fn(),
}));

describe('AdminDashboard', () => {
  it('should render the Approve button with the correct styling classes', async () => {
    // Setup mocks
    useAuth.mockReturnValue({ user: { email: 'admin@healthai.test' } });
    useLanguage.mockReturnValue({ t: (key) => key });
    
    api.getAdminDashboard.mockResolvedValue({
      total_patients: 10,
      total_doctors: 5,
      pending_verifications: 1,
      active_sessions: 2,
      verification_queue: [
        {
          id: 1,
          doctor_name: 'Dr. Test',
          specialization: 'General',
          experience_years: 5,
          contact: 'test@doctor.com',
          status: 'pending',
        },
      ],
      users: [],
    });

    api.getComplaints.mockResolvedValue([]);

    render(<AdminDashboard />);

    // Wait for the data to load and the table to render
    await waitFor(() => {
      expect(screen.getByText('Dr. Test')).toBeInTheDocument();
    });

    // Check for the Approve button
    const approveButton = screen.getByRole('button', { name: /Approve/i });
    expect(approveButton).toBeInTheDocument();
    
    // Verify that the Approve button is styled correctly so it's visible
    // Specifically checking that bg-success and text-white are present and not bg-dark text-on-secondary
    expect(approveButton).toHaveClass('bg-success');
    expect(approveButton).toHaveClass('text-white');
    expect(approveButton).not.toHaveClass('bg-dark');
  });
});
