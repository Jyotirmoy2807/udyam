import { useState, useRef, useEffect, useCallback } from "react";
import { api } from "../api/client";

interface UseSpeechOptions {
  language?: string; // hi, en, mr, etc.
  onTranscriptReady?: (text: string) => void;
}

export function useSpeech({ language = "en", onTranscriptReady }: UseSpeechOptions = {}) {
  const [isListening, setIsListening] = useState(false);
  const [isRecordingAudio, setIsRecordingAudio] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [isSpeaking, setIsSpeaking] = useState(false);

  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Map 2-letter language code to BCP-47 locale
  const getLocale = (code: string) => {
    switch (code) {
      case "hi":
        return "hi-IN";
      case "mr":
        return "mr-IN";
      case "ta":
        return "ta-IN";
      case "te":
        return "te-IN";
      case "kn":
        return "kn-IN";
      case "gu":
        return "gu-IN";
      case "bn":
        return "bn-IN";
      default:
        return "en-IN";
    }
  };

  // Initialize Web Speech API if supported
  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = getLocale(language);

      recognition.onstart = () => setIsListening(true);
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => setIsListening(false);

      recognition.onresult = (event: any) => {
        let currentText = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          currentText += event.results[i][0].transcript;
        }
        setTranscript(currentText);
        if (event.results[0].isFinal && onTranscriptReady) {
          onTranscriptReady(currentText);
        }
      };

      recognitionRef.current = recognition;
    }
  }, [language, onTranscriptReady]);

  // Start Web Speech API Recognition
  const startListening = useCallback(() => {
    if (recognitionRef.current) {
      setTranscript("");
      try {
        recognitionRef.current.lang = getLocale(language);
        recognitionRef.current.start();
      } catch {
        // Recognition already started
      }
    } else {
      // Fallback to MediaRecorder upload
      startRecordingAudio();
    }
  }, [language]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
  }, [isListening]);

  // Fallback: Audio blob recording for Groq Whisper endpoint
  const startRecordingAudio = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/wav" });
        setIsRecordingAudio(false);
        stream.getTracks().forEach((track) => track.stop());

        try {
          const res = await api.transcribeVoice(audioBlob, language);
          if (res.transcription) {
            setTranscript(res.transcription);
            if (onTranscriptReady) {
              onTranscriptReady(res.transcription);
            }
          }
        } catch {
          // Keep prior transcript
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecordingAudio(true);
    } catch {
      setIsRecordingAudio(false);
    }
  };

  const stopRecordingAudio = () => {
    if (mediaRecorderRef.current && isRecordingAudio) {
      mediaRecorderRef.current.stop();
    }
  };

  // Text-To-Speech Read-Aloud
  const speak = useCallback(
    (text: string) => {
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = getLocale(language);
        utterance.onstart = () => setIsSpeaking(true);
        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = () => setIsSpeaking(false);
        window.speechSynthesis.speak(utterance);
      }
    },
    [language]
  );

  return {
    isListening: isListening || isRecordingAudio,
    transcript,
    setTranscript,
    startListening,
    stopListening,
    startRecordingAudio,
    stopRecordingAudio,
    speak,
    isSpeaking,
  };
}
