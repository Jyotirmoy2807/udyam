import React, { createContext, useContext, useState, useEffect } from "react";
import { UserRole } from "../api/types";
import { setAuthToken } from "../api/client";

interface AuthContextType {
  token: string | null;
  role: UserRole;
  phoneMasked: string | null;
  activeLeadId: string | null;
  assistedMode: boolean;
  login: (token: string, role: UserRole, phoneMasked: string) => void;
  logout: () => void;
  setActiveLeadId: (leadId: string | null) => void;
  setAssistedMode: (enabled: boolean) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem("udyam_auth_token"));
  const [role, setRole] = useState<UserRole>(() => (sessionStorage.getItem("udyam_auth_role") as UserRole) || "customer");
  const [phoneMasked, setPhoneMasked] = useState<string | null>(() => sessionStorage.getItem("udyam_phone_masked"));
  const [activeLeadId, setActiveLeadIdState] = useState<string | null>(() => sessionStorage.getItem("udyam_active_lead_id"));
  const [assistedMode, setAssistedModeState] = useState<boolean>(() => sessionStorage.getItem("udyam_assisted_mode") === "true");

  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  const login = (newToken: string, newRole: UserRole, newPhoneMasked: string) => {
    setToken(newToken);
    setRole(newRole);
    setPhoneMasked(newPhoneMasked);
    sessionStorage.setItem("udyam_auth_token", newToken);
    sessionStorage.setItem("udyam_auth_role", newRole);
    sessionStorage.setItem("udyam_phone_masked", newPhoneMasked);
    setAuthToken(newToken);
  };

  const logout = () => {
    setToken(null);
    setRole("customer");
    setPhoneMasked(null);
    setActiveLeadIdState(null);
    setAssistedModeState(false);
    sessionStorage.clear();
    setAuthToken(null);
  };

  const setActiveLeadId = (leadId: string | null) => {
    setActiveLeadIdState(leadId);
    if (leadId) {
      sessionStorage.setItem("udyam_active_lead_id", leadId);
    } else {
      sessionStorage.removeItem("udyam_active_lead_id");
    }
  };

  const setAssistedMode = (enabled: boolean) => {
    setAssistedModeState(enabled);
    sessionStorage.setItem("udyam_assisted_mode", String(enabled));
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        role,
        phoneMasked,
        activeLeadId,
        assistedMode,
        login,
        logout,
        setActiveLeadId,
        setAssistedMode,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
