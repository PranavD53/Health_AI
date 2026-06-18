import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function Settings() {
  const { user, checkAuth } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saveLoading, setSaveLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  // Editable fields for patient
  const [name, setName] = useState('');
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState('Male');
  const [height, setHeight] = useState('');
  const [weight, setWeight] = useState('');
  const [allergies, setAllergies] = useState('');
  const [conditions, setConditions] = useState('');
  const [address, setAddress] = useState('');
  
  // Editable fields for doctor
  const [specialization, setSpecialization] = useState('General Medicine');
  const [experience, setExperience] = useState('');
  const [location, setLocation] = useState('');
  const [contact, setContact] = useState('');
  const [licenseNumber, setLicenseNumber] = useState('');
  const [licenseDocument, setLicenseDocument] = useState(null);
  const [profilePicture, setProfilePicture] = useState(null);
  const [existingLicensePath, setExistingLicensePath] = useState('');

  // Admin Request States
  const [adminRequestLoading, setAdminRequestLoading] = useState(false);
  const [adminRequestSuccess, setAdminRequestSuccess] = useState(false);
  const [adminRequestError, setAdminRequestError] = useState('');

  const handleRequestAdmin = async () => {
    setAdminRequestLoading(true);
    setAdminRequestError('');
    setAdminRequestSuccess(false);
    try {
      await api.requestAdmin();
      setAdminRequestSuccess(true);
      await checkAuth();
    } catch (err) {
      console.error(err);
      setAdminRequestError(err.message || 'Failed to submit promotion request.');
    } finally {
      setAdminRequestLoading(false);
    }
  };

  const loadProfile = async () => {
    if (!user) return;
    setLoading(true);
    try {
      if (user.role === 'patient') {
        const data = await api.getProfile();
        setName(data.name || '');
        setDob(data.date_of_birth || '');
        setGender(data.gender || 'Male');
        setHeight(data.height || '');
        setWeight(data.weight || '');
        setAllergies(data.allergies || '');
        setConditions(data.existing_conditions || '');
        setAddress(data.address || '');
      } else if (user.role === 'doctor') {
        const docs = await api.getDoctors();
        const doc = docs.find(d => d.user_id === user.id);
        if (doc) {
          setName(doc.name || '');
          setSpecialization(doc.specialization || 'General Medicine');
          setExperience(doc.experience_years || '');
          setLocation(doc.location || '');
          setAddress(doc.address || '');
          setContact(doc.contact || '');
          setLicenseNumber(doc.license_number || '');
          setExistingLicensePath(doc.license_document_path || '');
        }
      } else if (user.role === 'admin') {
        try {
          const data = await api.getProfile();
          setName(data.name || '');
          setAddress(data.address || '');
        } catch (err) {
          setName('');
          setAddress('');
        }
      }
    } catch (err) {
      console.error(err);
      setError("Failed to load profile settings.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, [user]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess(false);
    setSaveLoading(true);

    try {
      if (user.role === 'patient') {
        // Patient Profile Create / Update
        try {
          await api.getProfile();
          // Exists -> Update
          await api.updateProfile({
            name,
            date_of_birth: dob,
            gender,
            height: height ? parseFloat(height) : null,
            weight: weight ? parseFloat(weight) : null,
            allergies,
            existing_conditions: conditions,
            address
          });
        } catch (err) {
          // Doesn't exist -> Create
          await api.createProfile({
            name,
            date_of_birth: dob,
            gender,
            height: height ? parseFloat(height) : null,
            weight: weight ? parseFloat(weight) : null,
            allergies,
            existing_conditions: conditions,
            address
          });
        }
      } else if (user.role === 'doctor') {
        const formData = new FormData();
        formData.append('name', name);
        formData.append('specialization', specialization);
        formData.append('location', location);
        formData.append('experience_years', experience);
        formData.append('contact', contact || user.email);
        formData.append('address', address);
        formData.append('license_number', licenseNumber);
        if (licenseDocument) {
          formData.append('license_document', licenseDocument);
        }
        if (profilePicture) {
          formData.append('profile_picture', profilePicture);
        }
        
        await api.updateDoctorProfile(formData);
        
        // Reset file inputs
        setLicenseDocument(null);
        setProfilePicture(null);
        const licenseInput = document.getElementById('settings-license-input');
        const picInput = document.getElementById('settings-pic-input');
        if (licenseInput) licenseInput.value = '';
        if (picInput) picInput.value = '';
      } else if (user.role === 'admin') {
        try {
          await api.getProfile();
          await api.updateProfile({
            name,
            address
          });
        } catch (err) {
          await api.createProfile({
            name,
            address
          });
        }
      }
      
      setSuccess(true);
      await loadProfile();
      await checkAuth();
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error(err);
      setError("Failed to save settings: " + err.message);
    } finally {
      setSaveLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-xl animate-pulse">
        <div className="h-12 bg-surface-container rounded-xl w-1/3"></div>
        <div className="h-96 bg-surface-container rounded-xl"></div>
      </div>
    );
  }

  return (
    <div className="space-y-xl animate-in fade-in duration-300">
      <header>
        <h2 className="text-on-surface font-headline-lg text-headline-lg">
          Profile Settings
        </h2>
        <p className="text-on-surface-variant font-body-md text-body-md">Modify your personal settings, health attributes, and contact address details.</p>
      </header>

      {error && (
        <div className="p-4 bg-error-container text-on-error-container rounded-xl flex items-center gap-sm">
          <span className="material-symbols-outlined">error</span>
          <p>{error}</p>
        </div>
      )}

      {success && (
        <div className="p-4 bg-success/10 text-success rounded-xl flex items-center gap-sm font-bold text-sm">
          <span className="material-symbols-outlined">check_circle</span>
          <p>Profile details saved successfully!</p>
        </div>
      )}

      <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm overflow-hidden p-lg">
        <form onSubmit={handleSubmit} className="space-y-lg max-w-2xl">
          {user?.role === 'patient' && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Full Name</label>
                  <input 
                    required
                    type="text" 
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  />
                </div>
                
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Date of Birth</label>
                  <input 
                    type="date" 
                    value={dob}
                    onChange={(e) => setDob(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-md">
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Gender</label>
                  <select 
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm font-semibold"
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Height (cm)</label>
                  <input 
                    type="number" 
                    value={height}
                    onChange={(e) => setHeight(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                    placeholder="e.g. 172"
                  />
                </div>

                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Weight (kg)</label>
                  <input 
                    type="number" 
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                    placeholder="e.g. 65"
                  />
                </div>
              </div>

              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Allergies</label>
                <input 
                  type="text" 
                  value={allergies}
                  onChange={(e) => setAllergies(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  placeholder="e.g. Pollen, Penicillin"
                />
              </div>

              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Existing Medical Conditions</label>
                <textarea 
                  rows="2"
                  value={conditions}
                  onChange={(e) => setConditions(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  placeholder="e.g. Hypertension, Diabetes Type 2"
                />
              </div>

              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Home Address (Required for Emergency SOS Broadcasting)</label>
                <textarea 
                  required
                  rows="2"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  placeholder="e.g. 12 Park Avenue, Apartment 3B, New York"
                />
              </div>
            </>
          )}

          {user?.role === 'doctor' && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Full Name</label>
                  <input 
                    required
                    type="text" 
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  />
                </div>

                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Doctor ID / License Number *</label>
                  <input 
                    required
                    type="text" 
                    value={licenseNumber}
                    onChange={(e) => setLicenseNumber(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm font-semibold"
                  />
                </div>
              </div>
              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Clinic Location Room</label>
                <input 
                  required
                  type="text" 
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Specialization</label>
                  <select 
                    value={specialization}
                    onChange={(e) => setSpecialization(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm font-semibold"
                  >
                    <option value="Cardiology">Cardiology</option>
                    <option value="Dermatology">Dermatology</option>
                    <option value="General Medicine">General Medicine</option>
                    <option value="Neurology">Neurology</option>
                    <option value="Pediatrics">Pediatrics</option>
                  </select>
                </div>
                
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary ml-unit">Experience (Years)</label>
                  <input 
                    required
                    type="number" 
                    value={experience}
                    onChange={(e) => setExperience(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  />
                </div>
              </div>

              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Clinic Full Address</label>
                <textarea 
                  required
                  rows="3"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                />
              </div>

              {/* Upload Documents and Photos */}
              <div className="space-y-md border border-dashed border-outline-variant p-4 rounded-xl bg-surface">
                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary block">
                    Upload New Medical License Document (PDF/Image) *
                  </label>
                  <p className="text-[10px] text-outline mb-xs">
                    Uploading a new license resets your credentials verification back to pending.
                  </p>
                  <label className="flex items-center justify-between border border-outline-variant rounded-lg px-4 py-2.5 bg-surface hover:bg-surface-container-low cursor-pointer transition-colors text-xs text-on-surface-variant font-medium">
                    <span className="flex items-center gap-xs truncate max-w-[80%]">
                      <span className="material-symbols-outlined text-[18px] text-secondary">cloud_upload</span>
                      <span className="truncate">{licenseDocument ? licenseDocument.name : "Choose medical license..."}</span>
                    </span>
                    <span className="px-2.5 py-1 bg-secondary-container text-on-secondary-container rounded font-bold text-[10px] shrink-0">Browse</span>
                    <input 
                      id="settings-license-input"
                      type="file" 
                      accept=".pdf,image/*"
                      onChange={(e) => setLicenseDocument(e.target.files[0])}
                      className="hidden"
                    />
                  </label>
                  {existingLicensePath && (
                    <p className="text-[10px] text-secondary font-bold mt-1">
                      Current: <a href={`http://127.0.0.1:8000${existingLicensePath}`} target="_blank" rel="noopener noreferrer" className="hover:underline">View Active License Document</a>
                    </p>
                  )}
                </div>

                <div className="space-y-xs">
                  <label className="text-xs font-bold text-primary block">Upload New Profile Photo</label>
                  <label className="flex items-center justify-between border border-outline-variant rounded-lg px-4 py-2.5 bg-surface hover:bg-surface-container-low cursor-pointer transition-colors text-xs text-on-surface-variant font-medium">
                    <span className="flex items-center gap-xs truncate max-w-[80%]">
                      <span className="material-symbols-outlined text-[18px] text-secondary">photo_camera</span>
                      <span className="truncate">{profilePicture ? profilePicture.name : "Choose profile photo..."}</span>
                    </span>
                    <span className="px-2.5 py-1 bg-secondary-container text-on-secondary-container rounded font-bold text-[10px] shrink-0">Browse</span>
                    <input 
                      id="settings-pic-input"
                      type="file" 
                      accept="image/*"
                      onChange={(e) => setProfilePicture(e.target.files[0])}
                      className="hidden"
                    />
                  </label>
                </div>
              </div>
            </>
          )}

          {user?.role === 'admin' && (
            <>
              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Admin Full Name</label>
                <input 
                  required
                  type="text" 
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  placeholder="e.g. System Administrator"
                />
              </div>

              <div className="space-y-xs">
                <label className="text-xs font-bold text-primary ml-unit">Work / Office Address</label>
                <textarea 
                  required
                  rows="3"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-outline-variant bg-surface focus:outline-none focus:border-secondary text-sm"
                  placeholder="e.g. Platform HQ Office, 5th Floor, Medical Center"
                />
              </div>
            </>
          )}

          <button
            type="submit"
            disabled={saveLoading}
            className="px-6 py-3 bg-primary hover:bg-primary/95 text-white font-bold rounded-lg transition-colors flex items-center gap-xs focus:outline-none shadow-md"
          >
            {saveLoading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <>
                <span className="material-symbols-outlined">save</span>
                Save Profile
              </>
            )}
          </button>
        </form>
      </div>

      {user?.role !== 'admin' && (
        <div className="bg-white border border-outline-variant/30 rounded-2xl shadow-sm overflow-hidden p-lg mt-xl">
          <h3 className="text-on-surface font-title-lg text-title-lg mb-xs">Elevate Account Privileges</h3>
          <p className="text-on-surface-variant font-body-md text-body-md mb-lg">
            Request promotion to an Administrator role. Administrators can manage users, check verification statuses, and review clinical logs. Requests must be approved by the system superadmin.
          </p>
          {user?.admin_requested ? (
            <div className="inline-flex items-center gap-sm px-4 py-2 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm font-semibold">
              <span className="material-symbols-outlined animate-pulse text-amber-600">pending</span>
              Promotion Request Pending Approval
            </div>
          ) : (
            <button
              type="button"
              onClick={handleRequestAdmin}
              disabled={adminRequestLoading}
              className="px-6 py-2.5 bg-secondary hover:bg-secondary/95 disabled:bg-outline-variant text-white font-bold rounded-lg transition-colors flex items-center gap-xs focus:outline-none shadow-md"
            >
              {adminRequestLoading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              ) : (
                <>
                  <span className="material-symbols-outlined">admin_panel_settings</span>
                  Request Admin Role Promotion
                </>
              )}
            </button>
          )}
          {adminRequestSuccess && (
            <p className="text-success text-xs font-bold mt-sm flex items-center gap-xs">
              <span className="material-symbols-outlined text-sm">check_circle</span>
              Promotion request sent successfully!
            </p>
          )}
          {adminRequestError && (
            <p className="text-error text-xs font-bold mt-sm flex items-center gap-xs">
              <span className="material-symbols-outlined text-sm">error</span>
              {adminRequestError}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
