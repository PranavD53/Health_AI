import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../services/api';
import { useLanguage } from '../context/LanguageContext';

export default function DoctorSearch() {
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const [doctors, setDoctors] = useState([]);
  const [filteredDoctors, setFilteredDoctors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Search/Filter states
  const [searchTerm, setSearchTerm] = useState(searchParams.get('search') || '');
  const [selectedSpecialty, setSelectedSpecialty] = useState('All');
  const [onlyAvailable, setOnlyAvailable] = useState(false);

  // Booking Modal states
  const [bookingDoc, setBookingDoc] = useState(null);
  const [bookingDate, setBookingDate] = useState('');
  const [bookingTime, setBookingTime] = useState('10:00');
  const [bookingSuccess, setBookingSuccess] = useState(false);
  const [bookingLoading, setBookingLoading] = useState(false);

  const loadDoctors = async () => {
    setLoading(true);
    try {
      const data = await api.getDoctors();
      setDoctors(data);
    } catch (err) {
      console.error(err);
      setError("Failed to fetch doctors list.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDoctors();
  }, []);

  // Filter application logic
  useEffect(() => {
    let result = doctors;

    // Search term matching (Name, Location, Specialty)
    if (searchTerm) {
      const query = searchTerm.toLowerCase();
      result = result.filter(doc => 
        doc.name.toLowerCase().includes(query) ||
        doc.specialization.toLowerCase().includes(query) ||
        doc.location.toLowerCase().includes(query)
      );
    }

    // Specialty filter
    if (selectedSpecialty !== 'All') {
      result = result.filter(doc => doc.specialization === selectedSpecialty);
    }

    // Availability filter
    if (onlyAvailable) {
      result = result.filter(doc => doc.available);
    }

    setFilteredDoctors(result);
  }, [doctors, searchTerm, selectedSpecialty, onlyAvailable]);

  const handleOpenBooking = (doc) => {
    setBookingDoc(doc);
    setBookingSuccess(false);
    setBookingDate('');
  };

  const handleConfirmBooking = async (e) => {
    e.preventDefault();
    if (!bookingDate) {
      alert("Please select a date.");
      return;
    }

    setBookingLoading(true);
    try {
      await api.bookAppointment(bookingDoc.id, bookingDate, bookingTime);
      setBookingSuccess(true);
      setTimeout(() => {
        setBookingDoc(null);
        setBookingSuccess(false);
      }, 1500);
    } catch (err) {
      alert("Booking failed: " + err.message);
    } finally {
      setBookingLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-xl animate-pulse">
        <div className="h-12 bg-surface-container rounded-xl w-1/3"></div>
        <div className="h-16 bg-surface-container rounded-xl"></div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-lg">
          {[1, 2, 3].map(i => <div key={i} className="h-72 bg-surface-container rounded-xl"></div>)}
        </div>
      </div>
    );
  }

  const specialties = ['All', 'Cardiology', 'Dermatology', 'General Medicine', 'Neurology', 'Pediatrics'];

  return (
    <div className="space-y-xl animate-in fade-in duration-300">
      <header>
        <h2 className="text-on-surface font-headline-lg text-headline-lg">
          {t('appointments')}
        </h2>
        <p className="text-on-surface-variant font-body-md text-body-md">Search across verified clinical specialists and book appointments instantly.</p>
      </header>

      {error && (
        <div className="p-4 bg-error-container text-on-error-container rounded-xl flex items-center gap-sm">
          <span className="material-symbols-outlined">error</span>
          <p>{error}</p>
        </div>
      )}

      {/* Filter and Search Panel */}
      <div className="bg-white border border-outline-variant/30 p-lg rounded-2xl shadow-sm space-y-md interactive-card">
        <div className="flex flex-col md:flex-row gap-md">
          {/* Search Input */}
          <div className="flex-1 relative">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline">search</span>
            <input 
              type="text" 
              placeholder={t('searchDocPlaceholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm text-on-surface"
            />
          </div>
          
          {/* Specialty Dropdown */}
          <div className="w-full md:w-64">
            <select
              value={selectedSpecialty}
              onChange={(e) => setSelectedSpecialty(e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
            >
              {specialties.map(spec => (
                <option key={spec} value={spec}>{spec === 'All' ? 'All Specialities' : spec}</option>
              ))}
            </select>
          </div>

          {/* Availability Toggle */}
          <label className="flex items-center gap-sm cursor-pointer select-none">
            <input 
              type="checkbox" 
              checked={onlyAvailable}
              onChange={(e) => setOnlyAvailable(e.target.checked)}
              className="w-4 h-4 rounded text-secondary focus:ring-secondary border-outline-variant"
            />
            <span className="text-xs text-on-surface font-bold">Show Available Only</span>
          </label>
        </div>
      </div>

      {/* Doctors Grid */}
      {filteredDoctors.length === 0 ? (
        <div className="p-xl border border-dashed border-outline-variant rounded-2xl text-center text-outline bg-white">
          <span className="material-symbols-outlined text-5xl mb-xs">search_off</span>
          <p className="font-semibold text-sm">No specialists found matching your filter criteria.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-lg">
          {filteredDoctors.map(doc => (
            <div key={doc.id} className="bg-white border border-outline-variant/30 rounded-2xl overflow-hidden shadow-sm flex flex-col justify-between doctor-card hover:border-secondary/60 hover:shadow-md transition-all interactive-card">
              <div className="p-lg space-y-md">
                <div className="flex items-center gap-md">
                  <div className="w-16 h-16 rounded-full overflow-hidden border border-outline-variant bg-surface-container flex items-center justify-center shrink-0">
                    {doc.profile_picture ? (
                      <img 
                        alt={doc.name} 
                        src={doc.profile_picture.startsWith('http') ? doc.profile_picture : `http://127.0.0.1:8000${doc.profile_picture}`}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="material-symbols-outlined text-3xl text-outline">medical_services</span>
                    )}
                  </div>
                  <div>
                    <h3 className="font-bold text-on-surface text-base">{doc.name}</h3>
                    <p className="text-xs text-secondary font-bold">{doc.specialization}</p>
                    <p className="text-[10px] text-outline font-semibold">{doc.experience_years} Years Experience</p>
                  </div>
                </div>

                <div className="space-y-sm text-xs font-semibold text-on-surface-variant">
                  <div className="flex items-start gap-xs">
                    <span className="material-symbols-outlined text-[16px] text-secondary">home_pin</span>
                    <span>Location: {doc.location}</span>
                  </div>
                  <div className="flex items-center gap-xs">
                    <span className="material-symbols-outlined text-[16px] text-secondary">contact_mail</span>
                    <span>Email: {doc.contact}</span>
                  </div>
                  {doc.address && (
                    <div className="flex items-start gap-xs">
                      <span className="material-symbols-outlined text-[16px] text-secondary">location_on</span>
                      <span>Address: {doc.address}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="p-lg bg-surface border-t border-outline-variant/20 flex items-center justify-between">
                <span className={`px-2.5 py-0.5 rounded text-[10px] font-bold ${
                  doc.available ? 'bg-success/15 text-success' : 'bg-outline/20 text-outline'
                }`}>
                  {doc.available ? 'Available' : 'Unavailable'}
                </span>
                
                <button
                  disabled={!doc.available}
                  onClick={() => handleOpenBooking(doc)}
                  className={`px-4 py-2 font-bold text-xs rounded-lg transition-all focus:outline-none ${
                    doc.available 
                      ? 'bg-secondary text-white hover:bg-secondary/95 active:scale-95 shadow-sm'
                      : 'bg-outline-variant/40 text-outline cursor-not-allowed'
                  }`}
                >
                  Book Visit
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Booking Modal */}
      {bookingDoc && (
        <div className="fixed inset-0 bg-primary/20 backdrop-blur-sm flex items-center justify-center z-[100] animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl w-full max-w-md border border-outline-variant shadow-2xl overflow-hidden interactive-card">
            <div className="p-6 border-b border-outline-variant bg-surface flex justify-between items-center">
              <h3 className="font-bold text-primary text-title-md">Schedule Consultation</h3>
              <button 
                onClick={() => setBookingDoc(null)}
                className="p-1 hover:bg-surface-container-high rounded-full transition-colors text-outline focus:outline-none"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            {bookingSuccess ? (
              <div className="p-xl text-center space-y-md">
                <span className="material-symbols-outlined text-6xl text-success animate-bounce">check_circle</span>
                <div>
                  <h4 className="font-bold text-lg text-on-surface">Appointment Requested!</h4>
                  <p className="text-xs text-outline mt-xs">Your visit has been scheduled successfully.</p>
                </div>
              </div>
            ) : (
              <form onSubmit={handleConfirmBooking} className="p-6 space-y-md">
                <div className="flex items-center gap-md pb-md border-b border-outline-variant/30">
                  <div className="w-12 h-12 rounded-full overflow-hidden border border-outline-variant bg-surface-container flex items-center justify-center shrink-0">
                    {bookingDoc.profile_picture ? (
                      <img 
                        alt={bookingDoc.name} 
                        src={bookingDoc.profile_picture.startsWith('http') ? bookingDoc.profile_picture : `http://127.0.0.1:8000${bookingDoc.profile_picture}`} 
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="material-symbols-outlined text-2xl text-outline">person</span>
                    )}
                  </div>
                  <div>
                    <h4 className="font-bold text-on-surface">{bookingDoc.name}</h4>
                    <p className="text-xs text-secondary font-semibold">{bookingDoc.specialization}</p>
                  </div>
                </div>

                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Select Consultation Date</label>
                  <input 
                    required
                    type="date"
                    min={new Date().toISOString().split('T')[0]}
                    value={bookingDate}
                    onChange={(e) => setBookingDate(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm font-semibold text-on-surface"
                  />
                </div>

                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Select Time Slot</label>
                  <select
                    value={bookingTime}
                    onChange={(e) => setBookingTime(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm font-semibold text-on-surface"
                  >
                    <option value="09:00">09:00 AM</option>
                    <option value="09:30">09:30 AM</option>
                    <option value="10:00">10:00 AM</option>
                    <option value="10:30">10:30 AM</option>
                    <option value="11:00">11:00 AM</option>
                    <option value="11:30">11:30 AM</option>
                    <option value="12:00">12:00 PM</option>
                    <option value="14:00">02:00 PM</option>
                    <option value="14:30">02:30 PM</option>
                    <option value="15:00">03:00 PM</option>
                    <option value="15:30">03:30 PM</option>
                    <option value="16:00">04:00 PM</option>
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={bookingLoading}
                  className="w-full py-3 bg-secondary hover:bg-secondary/95 text-white font-bold rounded-lg transition-colors flex items-center justify-center gap-xs focus:outline-none shadow-md mt-md"
                >
                  {bookingLoading ? (
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <>
                      <span className="material-symbols-outlined">done</span>
                      Confirm Booking
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
