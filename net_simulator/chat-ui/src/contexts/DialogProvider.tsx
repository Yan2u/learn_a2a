import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import React, { useCallback, useState } from "react"
import { DialogContext } from "./DialogContext"
import { DialogClose } from "@radix-ui/react-dialog"


export const DialogProvider = ({ children }) => {

    // input dialog
    const [isInputDialogOpen, setIsInputDialogOpen] = useState(false);
    const [inputDialogDescription, setInputDialogDescription] = useState("");
    const [inputDialogTitle, setInputDialogTitle] = useState("");
    const [inputValue, setInputValue] = useState("");
    const [inputDialogCallback, setInputDialogCallback] = useState<(ok: boolean, value: string) => void | null>(null);

    const showInputDialog = useCallback((title: string, description: string, placeholder: string, callback: (ok: boolean, value: string) => void | null) => {
        setInputDialogTitle(title);
        setInputDialogDescription(description);
        setInputValue(placeholder);
        setInputDialogCallback(() => callback);
        setIsInputDialogOpen(true);
    }, []);

    const closeDialog = useCallback(() => {
        setIsInputDialogOpen(false);
        if (inputDialogCallback) {
            inputDialogCallback(false, "");
        }
    }, [])

    const inputDialogAction = (ok: boolean) => {
        setIsInputDialogOpen(false);
        if (inputDialogCallback) {
            inputDialogCallback(ok, inputValue);
        } else {
            console.warn("No callback provided for dialog action.");
        }
    }

    const [isMessageDialogOpen, setIsMessageDialogOpen] = useState(false);
    const [messageDialogTitle, setMessageDialogTitle] = useState("");
    const [messageDialogDescription, setMessageDialogDescription] = useState("");
    const [isOkOnly, setIsOkOnly] = useState(false);
    const [messageDialogCallback, setMessageDialogCallback] = useState<(ok: boolean) => void | null>(null);

    const showMessageDialog = useCallback((title: string, message: string, isOkOnly: boolean, callback: (ok: boolean) => void | null) => {
        setMessageDialogTitle(title);
        setMessageDialogDescription(message);
        setIsOkOnly(isOkOnly);
        setMessageDialogCallback(() => callback);
        setIsMessageDialogOpen(true);
    }, []);

    const messageDialogAction = (ok: boolean) => {
        setIsMessageDialogOpen(false);
        if (messageDialogCallback) {
            messageDialogCallback(ok);
        } else {
            console.warn("No callback provided for message dialog action.");
        }
    }

    const api = {
        showInputDialog,
        showMessageDialog,
        closeDialog
    };

    return (
        <DialogContext.Provider value={api}>
            {children}

            <Dialog open={isInputDialogOpen} onOpenChange={setIsInputDialogOpen}>
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>{inputDialogTitle}</DialogTitle>
                        <DialogDescription>
                            {inputDialogDescription}
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4">
                        <div className="grid gap-3">
                            <Label htmlFor="name-1">Value</Label>
                            <Input id="name-1" name="value"
                                value={inputValue} onChange={e => setInputValue(e.target.value)}
                                onSubmit={() => inputDialogAction(true)} />
                        </div>
                    </div>
                    <DialogFooter>
                        <DialogClose asChild>
                            <Button variant="outline" onClick={() => inputDialogAction(false)}>Cancel</Button>
                        </DialogClose>
                        <Button onClick={() => inputDialogAction(true)}>OK</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <Dialog open={isMessageDialogOpen} onOpenChange={setIsMessageDialogOpen}>
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>{messageDialogTitle}</DialogTitle>
                        <DialogDescription>
                            {messageDialogDescription}
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild>
                            <Button variant="outline" disabled={isOkOnly} onClick={() => inputDialogAction(false)}>
                                Cancel
                            </Button>
                        </DialogClose>
                        <Button onClick={() => messageDialogAction(true)}>OK</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </DialogContext.Provider>
    )
}