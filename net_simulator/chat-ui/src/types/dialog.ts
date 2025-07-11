
export type DialogContextType = {
    showInputDialog: (title: string, description: string, placeholder: string, callback: (ok: boolean, value: string) => void | null) => void,
    showMessageDialog: (title: string, message: string, isOkOnly: boolean, callback: (ok: boolean) => void | null) => void,
    closeDialog: () => void
}