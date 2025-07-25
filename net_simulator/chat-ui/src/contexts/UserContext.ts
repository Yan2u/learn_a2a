import { createContext } from 'react';
import { UserContextType } from '@/types';


export const UserContext = createContext<UserContextType | undefined>(undefined);