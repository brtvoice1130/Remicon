import React, { useState } from "react";
import axios from "axios";

// API URL 환경변수 설정 (개발: localhost, 프로덕션: Vercel /api)
const API_BASE_URL = import.meta.env.VITE_API_URL ||
  (window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/api');

function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState({
    prompt: "모든 페이지에서 레미콘 거래 데이터를 추출하여 현장명과 공급자명을 정확히 식별하고, 소계/합계 행은 제외해주세요."
  });
  const [search, setSearch] = useState("");
  const [notification, setNotification] = useState(null);
  const [savedData, setSavedData] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [showResultPopup, setShowResultPopup] = useState(false);
  const [aiExtractions, setAiExtractions] = useState([]);
  const [selectedExtraction, setSelectedExtraction] = useState(null);
  const [showAiDebug, setShowAiDebug] = useState(false);

  const showNotification = (message, type = "success") => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  const fetchSavedData = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/data/`);
      if (response.data.status === "success") {
        setSavedData(response.data.data);
      }
    } catch (error) {
      console.error("데이터 조회 실패:", error);
    }
  };

  const fetchStatistics = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/statistics/`);
      if (response.data.status === "success") {
        setStatistics(response.data.statistics);
      }
    } catch (error) {
      console.error("통계 조회 실패:", error);
    }
  };

  const fetchAiExtractions = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/ai-extractions/`);
      if (response.data.status === "success") {
        setAiExtractions(response.data.extractions);
      }
    } catch (error) {
      console.error("AI 추출 결과 조회 실패:", error);
    }
  };

  const fetchExtractionDetail = async (extractionId) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/ai-extractions/${extractionId}`);
      if (response.data.status === "success") {
        setSelectedExtraction(response.data.data);
      }
    } catch (error) {
      console.error("AI 추출 상세 조회 실패:", error);
    }
  };

  const testAiExtraction = async () => {
    if (!file) {
      showNotification("먼저 PDF 파일을 선택해주세요.", "error");
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      setLoading(true);
      const uploadResponse = await axios.post(`${API_BASE_URL}/upload_pdf/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      // API 할당량 소진 확인
      if (uploadResponse.data.status === "api_quota_exceeded") {
        showNotification(`⚠️ API 사용량 제한으로 프로그램 이용이 제한됩니다.\n${uploadResponse.data.recovery_time}에 다시 이용해주세요.`, "warning");
        return;
      }

      if (uploadResponse.data.status === "success") {
        const testResponse = await axios.post(
          `${API_BASE_URL}/ai-extractions/test/${uploadResponse.data.filename}`,
          null,
          { params: { prompt: settings.prompt } }
        );

        if (testResponse.data.status === "success") {
          setSelectedExtraction({
            filename: testResponse.data.filename,
            prompt: testResponse.data.prompt,
            extraction_time: new Date().toISOString(),
            ai_results: testResponse.data.ai_results,
            analysis: testResponse.data.analysis
          });
          setShowAiDebug(true);
          showNotification(`AI 추출 테스트 완료: ${testResponse.data.analysis.total_extracted}개 레코드`, "success");
        }
      }
    } catch (error) {
      console.error("AI 추출 테스트 실패:", error);
      // 429 상태 코드 (API 할당량 초과) 확인
      if (error.response && error.response.status === 429) {
        const responseData = error.response.data || {};
        showNotification(`⚠️ API 사용량 제한으로 프로그램 이용이 제한됩니다.\n${responseData.recovery_time || '매일 오전 9시'}에 다시 이용해주세요.`, "warning");
      } else {
        showNotification("AI 추출 테스트에 실패했습니다.", "error");
      }
    } finally {
      setLoading(false);
    }
  };

  const deleteDataItem = async (id) => {
    try {
      await axios.delete(`${API_BASE_URL}/data/${id}`);
      showNotification("데이터가 삭제되었습니다!");
      fetchSavedData();
      fetchStatistics();
    } catch (error) {
      showNotification("삭제 중 오류가 발생했습니다.", "error");
    }
  };

  const clearAllData = async () => {
    if (window.confirm('⚠️ 모든 데이터를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) {
      try {
        await axios.delete(`${API_BASE_URL}/data/`);
        showNotification("모든 데이터가 삭제되었습니다!");
        setSavedData([]);
        setStatistics({ total_records: 0, total_files: 0, total_amount: 0 });
      } catch (error) {
        showNotification("삭제 중 오류가 발생했습니다.", "error");
      }
    }
  };

  // 초기 로딩 시 데이터를 불러오지 않음 (수동 조회로 변경)

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setResult(null);
    setError("");
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("prompt", settings.prompt);
    try {
      const res = await axios.post(
        `${API_BASE_URL}/upload_pdf/`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data"
          }
        }
      );

      // API 할당량 소진 확인
      if (res.data.status === "api_quota_exceeded") {
        const errorMessage = `🚫 ${res.data.error}\n\n⏰ 복구 시간: ${res.data.recovery_time}\n💡 ${res.data.recovery_message}`;
        setError(errorMessage);
        showNotification(`⚠️ API 사용량 제한으로 프로그램 이용이 제한됩니다.\n${res.data.recovery_time}에 다시 이용해주세요.`, "warning");
        return;
      }

      // 기타 API 에러 확인
      if (res.data.status === "configuration_error") {
        setError(`🔧 ${res.data.error}\n📋 ${res.data.action_required}`);
        showNotification("API 설정 오류가 발생했습니다. 관리자에게 문의하세요.", "error");
        return;
      }

      if (res.data.status === "extraction_failed") {
        setError(`❌ ${res.data.error}\n💡 ${res.data.suggestion}`);
        showNotification("데이터 추출에 실패했습니다. 다른 PDF 파일을 시도해보세요.", "error");
        return;
      }

      // 실제 추출 데이터를 화면에 표시하고 팝업으로 결과 표시
      setResult(res.data);
      if (res.data.tables && res.data.tables.length > 0) {
        showNotification(`🤖 AI가 ${res.data.tables.length}개 레코드를 추출했습니다! 아래에서 확인하세요.`);
      } else {
        showNotification(`PDF를 업로드했지만 유효한 데이터가 없습니다.`, "warning");
      }
    } catch (err) {
      // 디버깅용 로그 추가
      console.log("업로드 에러 발생:", err);
      console.log("에러 응답:", err.response);
      console.log("에러 상태:", err.response?.status);
      console.log("에러 데이터:", err.response?.data);

      // 429 상태 코드 (API 할당량 초과) 확인
      if (err.response && err.response.status === 429) {
        const responseData = err.response.data || {};
        const errorMessage = `🚫 API 사용량 제한으로 프로그램 이용이 제한됩니다.\n⏰ 복구 시간: ${responseData.recovery_time || '매일 오전 9시'}\n💡 ${responseData.recovery_message || '복구 시간 이후에 다시 이용해주세요.'}`;
        setError(errorMessage);
        showNotification(`⚠️ API 사용량 제한으로 프로그램 이용이 제한됩니다.\n${responseData.recovery_time || '매일 오전 9시'}에 다시 이용해주세요.`, "warning");
      } else if (err.response?.data?.status === "api_quota_exceeded") {
        // 백엔드에서 직접 status를 확인
        const responseData = err.response.data;
        const errorMessage = `🚫 ${responseData.error}\n⏰ 복구 시간: ${responseData.recovery_time}\n💡 ${responseData.recovery_message}`;
        setError(errorMessage);
        showNotification(`⚠️ API 사용량 제한으로 프로그램 이용이 제한됩니다.\n${responseData.recovery_time}에 다시 이용해주세요.`, "warning");
      } else {
        setError("업로드 또는 추출 중 오류 발생");
        showNotification("오류가 발생했습니다. 다시 시도해주세요.", "error");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSettingsChange = (e) => {
    setSettings({ ...settings, [e.target.name]: e.target.value });
  };

  const filteredRows = result && result.tables
    ? result.tables.filter(row =>
        Object.values(row).some(
          v => v && v.toString().toLowerCase().includes(search.toLowerCase())
        )
      )
    : [];

  // 공급자별로 데이터 그룹화하고 소계 계산
  const groupBySupplier = (data) => {
    const groups = {};

    data.forEach(row => {
      const supplier = row.공급자 || row['supplier'] || '미분류';
      if (!groups[supplier]) {
        groups[supplier] = [];
      }
      groups[supplier].push(row);
    });

    return groups;
  };

  const calculateSubtotal = (rows) => {
    return rows.reduce((acc, row) => {
      const amount = parseFloat(row.공급가액 || row['amount'] || 0) || 0;
      const tax = parseFloat(row.세액 || row['tax_amount'] || 0) || 0;
      const total = parseFloat(row.합계 || row['total_amount'] || 0) || 0;
      const quantity = parseFloat(row.물량 || row['수량'] || row['quantity'] || 0) || 0;

      return {
        quantity: acc.quantity + quantity,
        amount: acc.amount + amount,
        tax: acc.tax + tax,
        total: acc.total + total,
        count: acc.count + 1
      };
    }, { quantity: 0, amount: 0, tax: 0, total: 0, count: 0 });
  };

  return (
    <>
      <style>
        {`
          :root {
            --primary: #3b82f6;
            --primary-dark: #2563eb;
            --secondary: #10b981;
            --secondary-dark: #059669;
            --danger: #ef4444;
            --warning: #f59e0b;
            --success: #10b981;
            --background: #f8fafc;
            --surface: #ffffff;
            --border: #e2e8f0;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
            --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
            --radius: 8px;
            --radius-lg: 12px;
          }

          * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
          }

          body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--background);
            color: var(--text-primary);
            line-height: 1.5;
          }

          .app-container {
            min-height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
          }

          .app-content {
            max-width: 1200px;
            margin: 0 auto;
            background: var(--surface);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-xl);
            overflow: hidden;
          }

          .app-header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            padding: 2rem;
            color: white;
            text-align: center;
          }

          .app-title {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(45deg, #fff, #e2e8f0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
          }

          .app-subtitle {
            font-size: 1.125rem;
            opacity: 0.9;
            font-weight: 400;
          }

          .upload-section {
            padding: 2rem;
            border-bottom: 1px solid var(--border);
          }

          .upload-area {
            border: 2px dashed var(--border);
            border-radius: var(--radius);
            padding: 3rem;
            text-align: center;
            transition: all 0.3s ease;
            cursor: pointer;
          }

          .upload-area:hover {
            border-color: var(--primary);
            background: #f8faff;
          }

          .upload-area.drag-over {
            border-color: var(--primary);
            background: #f0f9ff;
            transform: scale(1.02);
          }

          .upload-icon {
            font-size: 3rem;
            color: var(--primary);
            margin-bottom: 1rem;
          }

          .upload-text {
            font-size: 1.125rem;
            color: var(--text-secondary);
            margin-bottom: 1rem;
          }

          .file-input {
            display: none;
          }

          .upload-button {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: white;
            border: none;
            padding: 1rem 2rem;
            border-radius: var(--radius);
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: var(--shadow-md);
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
          }

          .upload-button:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
          }

          .upload-button:disabled {
            background: var(--text-secondary);
            cursor: not-allowed;
            transform: none;
            box-shadow: var(--shadow-sm);
          }

          .selected-file {
            margin-top: 1rem;
            padding: 1rem;
            background: #f0f9ff;
            border: 1px solid #bfdbfe;
            border-radius: var(--radius);
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--primary);
          }

          .controls-section {
            padding: 2rem;
            background: #fafbfc;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
          }

          .search-input {
            flex: 1;
            max-width: 300px;
            padding: 0.75rem 1rem;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            font-size: 1rem;
            transition: border-color 0.3s ease;
          }

          .search-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgb(59 130 246 / 0.1);
          }

          .button-group {
            display: flex;
            gap: 0.5rem;
          }

          .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: var(--radius);
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
          }

          .btn-secondary {
            background: var(--border);
            color: var(--text-primary);
          }

          .btn-secondary:hover {
            background: #d1d5db;
          }

          .btn-success {
            background: var(--success);
            color: white;
          }

          .btn-success:hover {
            background: var(--secondary-dark);
          }

          .btn-settings {
            background: var(--warning);
            color: white;
            position: absolute;
            top: 2rem;
            right: 2rem;
          }

          .results-section {
            padding: 2rem;
          }

          .results-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
          }

          .results-title {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
          }

          .results-count {
            font-size: 0.875rem;
            color: var(--text-secondary);
            background: #f1f5f9;
            padding: 0.5rem 1rem;
            border-radius: var(--radius);
          }

          .table-container {
            overflow-x: auto;
            border-radius: var(--radius);
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border);
          }

          .results-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
          }

          .results-table th,
          .results-table td {
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
          }

          .results-table th {
            background: #f8fafc;
            font-weight: 600;
            color: var(--text-primary);
            position: sticky;
            top: 0;
          }

          .results-table tbody tr:hover {
            background: #f8fafc;
          }

          .ocr-results {
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 2rem;
            margin-top: 2rem;
          }

          .ocr-text {
            white-space: pre-wrap;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.875rem;
            line-height: 1.6;
            color: var(--text-secondary);
          }

          .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            padding: 2rem;
          }

          .modal {
            background: white;
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-xl);
            width: 100%;
            max-width: 500px;
            max-height: 80vh;
            overflow: hidden;
            animation: modalSlideUp 0.3s ease-out;
          }

          @keyframes modalSlideUp {
            from {
              opacity: 0;
              transform: translateY(20px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }

          .modal-header {
            padding: 2rem 2rem 1rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
          }

          .modal-title {
            font-size: 1.5rem;
            font-weight: 600;
          }

          .modal-close {
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: var(--text-secondary);
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.3s ease;
          }

          .modal-close:hover {
            background: #f1f5f9;
          }

          .modal-body {
            padding: 2rem;
            max-height: 60vh;
            overflow-y: auto;
          }

          .form-group {
            margin-bottom: 1.5rem;
          }

          .form-label {
            display: block;
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
          }

          .form-input,
          .form-select,
          .form-textarea {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            font-size: 1rem;
            transition: border-color 0.3s ease;
          }

          .form-input:focus,
          .form-select:focus,
          .form-textarea:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgb(59 130 246 / 0.1);
          }

          .form-textarea {
            resize: vertical;
            min-height: 100px;
          }

          .notification {
            position: fixed;
            top: 2rem;
            right: 2rem;
            padding: 1rem 1.5rem;
            border-radius: var(--radius);
            color: white;
            font-weight: 500;
            box-shadow: var(--shadow-lg);
            z-index: 1001;
            animation: slideInRight 0.3s ease-out;
            max-width: 400px;
          }

          @keyframes slideInRight {
            from {
              opacity: 0;
              transform: translateX(100%);
            }
            to {
              opacity: 1;
              transform: translateX(0);
            }
          }

          .notification.success {
            background: var(--success);
          }

          .notification.error {
            background: var(--danger);
          }

          .notification.warning {
            background: var(--warning);
          }

          .error-message {
            background: #fef2f2;
            border: 1px solid #fecaca;
            color: #dc2626;
            padding: 1rem;
            border-radius: var(--radius);
            margin-top: 1rem;
          }

          .loading-spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #ffffff3d;
            border-top: 2px solid #ffffff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
          }

          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }

          @media (max-width: 768px) {
            .app-container {
              padding: 1rem;
            }

            .upload-section,
            .controls-section,
            .results-section {
              padding: 1.5rem;
            }

            .app-title {
              font-size: 2rem;
            }

            .controls-section {
              flex-direction: column;
              align-items: stretch;
            }

            .search-input {
              max-width: none;
            }

            .btn-settings {
              position: static;
              margin-bottom: 1rem;
              align-self: flex-end;
            }

            .saved-table {
              font-size: 0.75rem;
            }

            .saved-table th,
            .saved-table td {
              padding: 0.5rem 0.25rem;
            }
          }

          .saved-data-section {
            padding: 2rem;
            border-top: 1px solid var(--border);
            background: #fafbfc;
          }

          .stats-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
          }

          .stats-card {
            background: white;
            padding: 1.5rem;
            border-radius: var(--radius);
            box-shadow: var(--shadow-sm);
            text-align: center;
          }

          .stats-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 0.5rem;
          }

          .stats-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            font-weight: 500;
          }

          .saved-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: var(--shadow-sm);
          }

          .saved-table th {
            background: var(--primary);
            color: white;
            padding: 1rem 0.75rem;
            font-size: 0.875rem;
            font-weight: 600;
            text-align: center;
            white-space: nowrap;
          }

          .saved-table td {
            padding: 0.75rem;
            border-bottom: 1px solid var(--border);
            font-size: 0.875rem;
            text-align: center;
          }

          .saved-table tbody tr:hover {
            background: #f8fafc;
          }

          .amount-cell {
            font-weight: 600;
            color: var(--primary);
          }

          .delete-btn {
            background: var(--danger);
            color: white;
            border: none;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.3s ease;
          }

          .delete-btn:hover {
            background: #dc2626;
            transform: scale(1.05);
          }

          .no-data {
            text-align: center;
            padding: 3rem;
            color: var(--text-secondary);
            background: white;
            border-radius: var(--radius);
            box-shadow: var(--shadow-sm);
          }

          .table-scroll {
            overflow-x: auto;
          }

          .extraction-results-section {
            padding: 2rem;
            border-bottom: 1px solid var(--border);
            background: linear-gradient(135deg, #f8faff 0%, #f0f9ff 100%);
          }

          .extraction-stats {
            display: flex;
            gap: 1rem;
            align-items: center;
            flex-wrap: wrap;
            margin-top: 0.5rem;
          }

          .stat-item {
            background: linear-gradient(135deg, var(--secondary) 0%, var(--secondary-dark) 100%);
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
            box-shadow: var(--shadow-sm);
          }

          .extracted-table {
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: var(--shadow-md);
          }

          .extracted-table th {
            background: linear-gradient(135deg, var(--secondary) 0%, var(--secondary-dark) 100%);
            color: white;
            padding: 1rem 0.75rem;
            text-align: left;
            font-weight: 600;
            font-size: 0.875rem;
            border: none;
          }

          .extracted-table td {
            padding: 0.875rem 0.75rem;
            border-bottom: 1px solid var(--border);
            font-size: 0.875rem;
            vertical-align: top;
          }

          .extracted-table tbody tr:hover {
            background: #f1f5f9;
            transition: background-color 0.2s ease;
          }

          .extracted-table tbody tr:last-child td {
            border-bottom: none;
          }

          .no-results {
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-style: italic;
            background: var(--surface);
            border-radius: var(--radius);
            margin-top: 1rem;
          }

          /* AI Debug Section Styles */
          .ai-debug-section {
            background: var(--surface);
            border-radius: var(--radius-lg);
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: var(--shadow-md);
          }

          .debug-controls {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
          }

          .btn-debug {
            background: var(--warning);
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: var(--radius);
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
          }

          .btn-debug:hover {
            background: #d97706;
            transform: translateY(-2px);
          }

          .btn-debug:disabled {
            background: var(--text-secondary);
            cursor: not-allowed;
            transform: none;
          }

          .ai-debug-modal {
            width: 90%;
            max-width: 1200px;
            max-height: 90vh;
            overflow-y: auto;
          }

          .debug-info {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
          }

          .debug-summary {
            background: #f8fafc;
            padding: 1rem;
            border-radius: var(--radius);
            border: 1px solid var(--border);
          }

          .debug-summary h4 {
            margin-bottom: 1rem;
            color: var(--text-primary);
          }

          .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 0.75rem;
          }

          .info-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem;
            background: white;
            border-radius: var(--radius);
            border: 1px solid #e2e8f0;
          }

          .info-item .label {
            font-weight: 600;
            color: var(--text-secondary);
            font-size: 0.875rem;
          }

          .info-item .value {
            font-weight: 700;
            color: var(--text-primary);
          }

          .suppliers-info {
            background: #f0f9ff;
            padding: 1rem;
            border-radius: var(--radius);
            border: 1px solid #bfdbfe;
          }

          .suppliers-info h4 {
            margin-bottom: 0.75rem;
            color: var(--primary);
          }

          .suppliers-list {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
          }

          .supplier-tag {
            background: var(--primary);
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 1rem;
            font-size: 0.875rem;
            font-weight: 500;
          }

          .raw-data-section {
            background: #fefefe;
            padding: 1rem;
            border-radius: var(--radius);
            border: 1px solid var(--border);
          }

          .raw-data-section h4 {
            margin-bottom: 1rem;
            color: var(--text-primary);
          }

          .raw-data-scroll {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid var(--border);
            border-radius: var(--radius);
          }

          .raw-data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
          }

          .raw-data-table th {
            background: #f1f5f9;
            padding: 0.75rem 0.5rem;
            text-align: left;
            font-weight: 600;
            color: var(--text-primary);
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 1;
          }

          .raw-data-table td {
            padding: 0.5rem;
            border-bottom: 1px solid #f1f5f9;
            vertical-align: top;
          }

          .incomplete-row {
            background: #fef2f2;
          }

          .incomplete-row td {
            color: #991b1b;
          }

          .status.complete {
            color: var(--success);
            font-weight: 700;
          }

          .status.incomplete {
            color: var(--danger);
            font-weight: 700;
          }

          /* 공급자별 소계 및 전체 합계 스타일 */
          .supplier-subtotal td {
            border-top: 2px solid #cbd5e1;
            border-bottom: 1px solid #cbd5e1;
          }

          .grand-total td {
            border-top: 3px solid #059669;
            border-bottom: 2px solid #059669;
          }

          .extracted-table .supplier-subtotal:hover td,
          .saved-table .supplier-subtotal:hover td {
            background: #e2e8f0 !important;
          }

          .extracted-table .grand-total:hover td,
          .saved-table .grand-total:hover td {
            background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
          }
        `}
      </style>

      <div className="app-container">
        <div className="app-content">
          {/* Header */}
          <div className="app-header">
            <h1 className="app-title">📄 Remicon</h1>
            <p className="app-subtitle">PDF 데이터 추출 도구</p>
            <button
              className="btn btn-settings"
              onClick={() => setShowSettings(true)}
            >
              📝 프롬프트
            </button>
          </div>

          {/* Upload Section */}
          <div className="upload-section">
            <div className="upload-area" onClick={() => document.getElementById('fileInput').click()}>
              <div className="upload-icon">📁</div>
              <p className="upload-text">
                {file ? '다른 파일을 선택하려면 클릭하세요' : 'PDF 파일을 드래그하거나 클릭하여 선택하세요'}
              </p>
              <input
                id="fileInput"
                type="file"
                accept="application/pdf,image/*"
                onChange={handleFileChange}
                className="file-input"
              />
              <button
                className="upload-button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleUpload();
                }}
                disabled={loading || !file}
              >
                {loading ? (
                  <>
                    <span className="loading-spinner"></span>
                    업로드 중...
                  </>
                ) : (
                  <>
                    🚀 업로드 및 추출
                  </>
                )}
              </button>
            </div>

            {file && (
              <div className="selected-file">
                📎 {file.name}
              </div>
            )}

            {error && (
              <div className="error-message">
                ❌ {error}
              </div>
            )}
          </div>

          {/* AI Debug Section */}
          <div className="ai-debug-section">
            <div className="debug-controls">
              <button
                className="btn btn-debug"
                onClick={testAiExtraction}
                disabled={loading || !file}
              >
                🔍 AI 추출 디버그
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  fetchAiExtractions();
                  setShowAiDebug(true);
                }}
              >
                📊 추출 내역 조회
              </button>
            </div>
          </div>

          {/* AI Debug Modal */}
          {showAiDebug && selectedExtraction && (
            <div className="modal-overlay" onClick={() => setShowAiDebug(false)}>
              <div className="modal-content ai-debug-modal" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                  <h3>🔍 AI 추출 결과 분석</h3>
                  <button
                    className="btn btn-close"
                    onClick={() => setShowAiDebug(false)}
                  >
                    ✕
                  </button>
                </div>

                <div className="debug-info">
                  <div className="debug-summary">
                    <h4>📋 추출 정보</h4>
                    <div className="info-grid">
                      <div className="info-item">
                        <span className="label">파일명:</span>
                        <span className="value">{selectedExtraction.filename}</span>
                      </div>
                      <div className="info-item">
                        <span className="label">추출 시간:</span>
                        <span className="value">
                          {new Date(selectedExtraction.extraction_time).toLocaleString('ko-KR')}
                        </span>
                      </div>
                      <div className="info-item">
                        <span className="label">총 추출 레코드:</span>
                        <span className="value">{selectedExtraction.analysis?.total_extracted || selectedExtraction.ai_results?.length}</span>
                      </div>
                      <div className="info-item">
                        <span className="label">완전한 레코드:</span>
                        <span className="value">{selectedExtraction.analysis?.complete_records || 0}</span>
                      </div>
                      <div className="info-item">
                        <span className="label">빈 레코드:</span>
                        <span className="value">{selectedExtraction.analysis?.empty_records || 0}</span>
                      </div>
                    </div>
                  </div>

                  <div className="suppliers-info">
                    <h4>🏢 발견된 공급자</h4>
                    <div className="suppliers-list">
                      {selectedExtraction.analysis?.suppliers?.map((supplier, index) => (
                        <span key={index} className="supplier-tag">
                          {supplier || '(빈 값)'}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="raw-data-section">
                    <h4>📄 원본 AI 추출 데이터 (처음 10개)</h4>
                    <div className="raw-data-scroll">
                      <table className="raw-data-table">
                        <thead>
                          <tr>
                            <th>순번</th>
                            <th>공급자</th>
                            <th>품명</th>
                            <th>규격</th>
                            <th>물량</th>
                            <th>단가</th>
                            <th>공급가액</th>
                            <th>완전성</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedExtraction.ai_results?.slice(0, 10).map((item, index) => (
                            <tr key={index} className={!item.품명 || !item.공급자 ? 'incomplete-row' : ''}>
                              <td>{index + 1}</td>
                              <td>{item.공급자 || '(빈 값)'}</td>
                              <td>{item.품명 || '(빈 값)'}</td>
                              <td>{item.규격 || '(빈 값)'}</td>
                              <td>{item.물량 || '(빈 값)'}</td>
                              <td>{item.단가 ? item.단가.toLocaleString() : '(빈 값)'}</td>
                              <td>{item.공급가액 ? item.공급가액.toLocaleString() : '(빈 값)'}</td>
                              <td>
                                <span className={`status ${item.품명 && item.공급자 && item.공급가액 ? 'complete' : 'incomplete'}`}>
                                  {item.품명 && item.공급자 && item.공급가액 ? '✅' : '❌'}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* AI Extraction Results Section */}
          {result && result.tables && result.tables.length > 0 && (
            <div className="extraction-results-section">
              <div className="results-header">
                <h2 className="results-title">🤖 AI 추출 결과</h2>
                <div className="extraction-stats">
                  <span className="stat-item">
                    📊 총 {result.tables.length}개 레코드 추출됨
                  </span>
                  {result.saved_count && (
                    <span className="stat-item">
                      💾 {result.saved_count}개 DB 저장됨
                    </span>
                  )}
                </div>
              </div>

              <div className="controls-section">
                <input
                  type="text"
                  placeholder="🔍 추출된 데이터 검색..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="search-input"
                />
              </div>

              <div className="table-scroll">
                <table className="extracted-table">
                  <thead>
                    <tr>
                      <th>순번</th>
                      <th>현장명</th>
                      <th>공급자</th>
                      <th>품명</th>
                      <th>규격</th>
                      <th>단위</th>
                      <th>물량</th>
                      <th>단가</th>
                      <th>공급가액</th>
                      <th>세액</th>
                      <th>합계</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(() => {
                      const groupedData = groupBySupplier(filteredRows);
                      const tableRows = [];
                      let globalIndex = 1;

                      Object.entries(groupedData).forEach(([supplier, rows]) => {
                        // 공급자별 데이터 행들
                        rows.forEach((row, index) => {
                          tableRows.push(
                            <tr key={`${supplier}-${index}`}>
                              <td>{globalIndex++}</td>
                              <td>{row.현장명 || row['현장'] || '-'}</td>
                              <td>{row.공급자 || row['supplier'] || '-'}</td>
                              <td>{row.품명 || row['품목'] || row['제품명'] || '-'}</td>
                              <td>{row.규격 || row['specification'] || '-'}</td>
                              <td>{row.단위 || row['unit'] || '-'}</td>
                              <td>{row.물량 || row['수량'] || row['quantity'] || '-'}</td>
                              <td className="amount-cell">
                                {row.단가 || row['unit_price'] || '-'}
                              </td>
                              <td className="amount-cell">
                                {(row.공급가액 || row['amount']) ?
                                  new Intl.NumberFormat('ko-KR').format(parseFloat(row.공급가액 || row['amount'])) : '-'}
                              </td>
                              <td className="amount-cell">
                                {(row.세액 || row['tax_amount']) ?
                                  new Intl.NumberFormat('ko-KR').format(parseFloat(row.세액 || row['tax_amount'])) : '-'}
                              </td>
                              <td className="amount-cell">
                                {(row.합계 || row['total_amount']) ?
                                  new Intl.NumberFormat('ko-KR').format(parseFloat(row.합계 || row['total_amount'])) : '-'}
                              </td>
                            </tr>
                          );
                        });

                        // 공급자별 소계 행
                        if (rows.length > 1) {
                          const subtotal = calculateSubtotal(rows);
                          tableRows.push(
                            <tr key={`${supplier}-subtotal`} className="supplier-subtotal">
                              <td colSpan="6" style={{
                                background: '#f1f5f9',
                                fontWeight: '600',
                                textAlign: 'right',
                                color: '#1e293b'
                              }}>
                                🏢 {supplier} 소계 ({subtotal.count}건)
                              </td>
                              <td style={{ background: '#f1f5f9', fontWeight: '600', textAlign: 'center' }}>
                                {subtotal.quantity > 0 ? new Intl.NumberFormat('ko-KR').format(subtotal.quantity) : '-'}
                              </td>
                              <td style={{ background: '#f1f5f9' }}></td>
                              <td className="amount-cell" style={{ background: '#f1f5f9', fontWeight: '600', color: '#3b82f6' }}>
                                {subtotal.amount > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(subtotal.amount)) : '-'}
                              </td>
                              <td className="amount-cell" style={{ background: '#f1f5f9', fontWeight: '600', color: '#f59e0b' }}>
                                {subtotal.tax > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(subtotal.tax)) : '-'}
                              </td>
                              <td className="amount-cell" style={{ background: '#f1f5f9', fontWeight: '700', color: '#10b981' }}>
                                {subtotal.total > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(subtotal.total)) : '-'}
                              </td>
                            </tr>
                          );
                        }
                      });

                      // 전체 합계 행
                      if (filteredRows.length > 0) {
                        const grandTotal = calculateSubtotal(filteredRows);
                        tableRows.push(
                          <tr key="grand-total" className="grand-total">
                            <td colSpan="6" style={{
                              background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                              color: 'white',
                              fontWeight: '700',
                              textAlign: 'right'
                            }}>
                              📊 전체 합계 ({grandTotal.count}건)
                            </td>
                            <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: 'white', fontWeight: '700', textAlign: 'center' }}>
                              {grandTotal.quantity > 0 ? new Intl.NumberFormat('ko-KR').format(grandTotal.quantity) : '-'}
                            </td>
                            <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}></td>
                            <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: 'white', fontWeight: '700', textAlign: 'right' }}>
                              {grandTotal.amount > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(grandTotal.amount)) : '-'}
                            </td>
                            <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: 'white', fontWeight: '700', textAlign: 'right' }}>
                              {grandTotal.tax > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(grandTotal.tax)) : '-'}
                            </td>
                            <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: 'white', fontWeight: '700', textAlign: 'right' }}>
                              {grandTotal.total > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(grandTotal.total)) : '-'}
                            </td>
                          </tr>
                        );
                      }

                      return tableRows;
                    })()}
                  </tbody>
                </table>
              </div>

              {filteredRows.length === 0 && result.tables.length > 0 && (
                <div className="no-results">
                  🔍 검색 결과가 없습니다.
                </div>
              )}
            </div>
          )}

          {/* Data Management Section */}
          <div className="saved-data-section">
            <div className="results-header">
              <h2 className="results-title">📊 데이터 관리</h2>
              <div className="button-group">
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    fetchSavedData();
                    fetchStatistics();
                    showNotification("데이터를 조회했습니다!");
                  }}
                >
                  🔍 조회
                </button>
                <button
                  className="btn btn-success"
                  onClick={() => {
                    // CSV 다운로드
                    const headers = ['날짜(출하일)', '현장명(납기장소)', '공급자(상호)', '품명', '규격', '단위', '물량', '단가', '공급가액', '세액', '합계', '통화'];
                    const csvData = [headers.join(',')].concat(
                      savedData.map(item => [
                        item.upload_date,
                        item.site_name || '',
                        item.supplier || '',
                        item.item_name || '',
                        item.specification || '',
                        item.unit || '',
                        item.quantity || '',
                        item.unit_price || '',
                        item.amount || '',
                        item.tax_amount || '',
                        item.total_amount || '',
                        item.currency || 'KRW'
                      ].map(v => '"' + String(v).replace(/"/g, '""') + '"').join(','))
                    ).join('\n');
                    const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `remicon_data_${new Date().toISOString().split('T')[0]}.csv`;
                    a.click();
                    URL.revokeObjectURL(url);
                    showNotification("CSV 파일이 다운로드되었습니다!");
                  }}
                  disabled={savedData.length === 0}
                >
                  📥 전체 다운로드
                </button>
                <button
                  className="btn"
                  style={{ background: '#ef4444', color: 'white' }}
                  onClick={clearAllData}
                  disabled={savedData.length === 0}
                >
                  🗑️ 전체 삭제
                </button>
              </div>
            </div>

            <div className="table-scroll">
              <table className="saved-table">
                <thead>
                  <tr>
                    <th>날짜(출하일)</th>
                    <th>현장명(납기장소)</th>
                    <th>공급자(상호)</th>
                    <th>품명</th>
                    <th>규격</th>
                    <th>단위</th>
                    <th>물량</th>
                    <th>단가</th>
                    <th>금액(공급가액)</th>
                    <th>세액</th>
                    <th>합계</th>
                    <th>통화</th>
                    <th>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {savedData.length > 0 ? (() => {
                    // 저장된 데이터를 공급자별로 그룹화
                    const groupedSavedData = {};
                    savedData.forEach(item => {
                      const supplier = item.supplier || '미분류';
                      if (!groupedSavedData[supplier]) {
                        groupedSavedData[supplier] = [];
                      }
                      groupedSavedData[supplier].push(item);
                    });

                    const tableRows = [];

                    Object.entries(groupedSavedData).forEach(([supplier, items]) => {
                      // 공급자별 데이터 행들
                      items.forEach((item) => {
                        tableRows.push(
                          <tr key={item.id}>
                            <td>{item.upload_date}</td>
                            <td>{item.site_name || '-'}</td>
                            <td>{item.supplier || '-'}</td>
                            <td>{item.item_name || '-'}</td>
                            <td>{item.specification || '-'}</td>
                            <td>{item.unit || '-'}</td>
                            <td>{item.quantity > 0 ? item.quantity.toLocaleString() : '-'}</td>
                            <td className="amount-cell">
                              {item.unit_price > 0 ?
                                new Intl.NumberFormat('ko-KR').format(Math.round(item.unit_price)) : '-'}
                            </td>
                            <td className="amount-cell">
                              {item.amount > 0 ?
                                new Intl.NumberFormat('ko-KR').format(Math.round(item.amount)) : '-'}
                            </td>
                            <td className="amount-cell">
                              {item.tax_amount > 0 ?
                                new Intl.NumberFormat('ko-KR').format(Math.round(item.tax_amount)) : '-'}
                            </td>
                            <td className="amount-cell">
                              {item.total_amount > 0 ?
                                new Intl.NumberFormat('ko-KR').format(Math.round(item.total_amount)) : '-'}
                            </td>
                            <td>KRW</td>
                            <td>
                              <button
                                className="delete-btn"
                                onClick={() => {
                                  if (window.confirm('이 항목을 삭제하시겠습니까?')) {
                                    deleteDataItem(item.id);
                                  }
                                }}
                                title="삭제"
                              >
                                🗑️
                              </button>
                            </td>
                          </tr>
                        );
                      });

                      // 공급자별 소계 행
                      if (items.length > 1) {
                        const subtotal = items.reduce((acc, item) => ({
                          quantity: acc.quantity + (item.quantity || 0),
                          amount: acc.amount + (item.amount || 0),
                          tax: acc.tax + (item.tax_amount || 0),
                          total: acc.total + (item.total_amount || 0),
                          count: acc.count + 1
                        }), { quantity: 0, amount: 0, tax: 0, total: 0, count: 0 });

                        tableRows.push(
                          <tr key={`${supplier}-subtotal`} className="supplier-subtotal">
                            <td colSpan="6" style={{
                              background: '#f1f5f9',
                              fontWeight: '600',
                              textAlign: 'right',
                              color: '#1e293b'
                            }}>
                              🏢 {supplier} 소계 ({subtotal.count}건)
                            </td>
                            <td style={{ background: '#f1f5f9', fontWeight: '600', textAlign: 'center' }}>
                              {subtotal.quantity > 0 ? new Intl.NumberFormat('ko-KR').format(subtotal.quantity) : '-'}
                            </td>
                            <td style={{ background: '#f1f5f9' }}></td>
                            <td className="amount-cell" style={{ background: '#f1f5f9', fontWeight: '600', color: '#3b82f6' }}>
                              {subtotal.amount > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(subtotal.amount)) : '-'}
                            </td>
                            <td className="amount-cell" style={{ background: '#f1f5f9', fontWeight: '600', color: '#f59e0b' }}>
                              {subtotal.tax > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(subtotal.tax)) : '-'}
                            </td>
                            <td className="amount-cell" style={{ background: '#f1f5f9', fontWeight: '700', color: '#10b981' }}>
                              {subtotal.total > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(subtotal.total)) : '-'}
                            </td>
                            <td style={{ background: '#f1f5f9' }}>KRW</td>
                            <td style={{ background: '#f1f5f9' }}></td>
                          </tr>
                        );
                      }
                    });

                    // 전체 합계 행
                    if (savedData.length > 0) {
                      const grandTotal = savedData.reduce((acc, item) => ({
                        quantity: acc.quantity + (item.quantity || 0),
                        amount: acc.amount + (item.amount || 0),
                        tax: acc.tax + (item.tax_amount || 0),
                        total: acc.total + (item.total_amount || 0),
                        count: acc.count + 1
                      }), { quantity: 0, amount: 0, tax: 0, total: 0, count: 0 });

                      tableRows.push(
                        <tr key="grand-total" className="grand-total">
                          <td colSpan="6" style={{
                            background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                            color: 'white',
                            fontWeight: '700',
                            textAlign: 'right'
                          }}>
                            📊 전체 합계 ({grandTotal.count}건)
                          </td>
                          <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: 'white', fontWeight: '700', textAlign: 'center' }}>
                            {grandTotal.quantity > 0 ? new Intl.NumberFormat('ko-KR').format(grandTotal.quantity) : '-'}
                          </td>
                          <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}></td>
                          <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: 'white', fontWeight: '700', textAlign: 'right' }}>
                            {grandTotal.amount > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(grandTotal.amount)) : '-'}
                          </td>
                          <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: 'white', fontWeight: '700', textAlign: 'right' }}>
                            {grandTotal.tax > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(grandTotal.tax)) : '-'}
                          </td>
                          <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: 'white', fontWeight: '700', textAlign: 'right' }}>
                            {grandTotal.total > 0 ? new Intl.NumberFormat('ko-KR').format(Math.round(grandTotal.total)) : '-'}
                          </td>
                          <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: 'white' }}>KRW</td>
                          <td style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}></td>
                        </tr>
                      );
                    }

                    return tableRows;
                  })() : (
                    <tr>
                      <td colSpan="13" style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
                        <div>
                          <p style={{ fontSize: '1.125rem', marginBottom: '0.5rem' }}>📋 데이터가 없습니다</p>
                          <p style={{ fontSize: '0.875rem' }}>PDF를 업로드하면 추출된 데이터가 여기에 표시됩니다</p>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Summary Footer */}
            {savedData.length > 0 && (
              <div style={{
                marginTop: '1rem',
                padding: '1rem',
                background: 'white',
                borderRadius: '8px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '1rem'
              }}>
                <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
                  <div>
                    <span style={{ fontWeight: '600' }}>총 항목: </span>
                    <span style={{ color: '#3b82f6' }}>{savedData.length}개</span>
                  </div>
                  <div>
                    <span style={{ fontWeight: '600' }}>총 공급가액: </span>
                    <span style={{ color: '#10b981', fontWeight: '600' }}>
                      {new Intl.NumberFormat('ko-KR').format(
                        Math.round(savedData.reduce((sum, item) => sum + (item.amount || 0), 0))
                      )}원
                    </span>
                  </div>
                  <div>
                    <span style={{ fontWeight: '600' }}>총 세액: </span>
                    <span style={{ color: '#f59e0b', fontWeight: '600' }}>
                      {new Intl.NumberFormat('ko-KR').format(
                        Math.round(savedData.reduce((sum, item) => sum + (item.tax_amount || 0), 0))
                      )}원
                    </span>
                  </div>
                  <div>
                    <span style={{ fontWeight: '600' }}>총 합계: </span>
                    <span style={{ color: '#3b82f6', fontWeight: '700', fontSize: '1.125rem' }}>
                      {new Intl.NumberFormat('ko-KR').format(
                        Math.round(savedData.reduce((sum, item) => sum + (item.total_amount || 0), 0))
                      )}원
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Settings Modal */}
        {showSettings && (
          <div className="modal-overlay" onClick={() => setShowSettings(false)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2 className="modal-title">📝 프롬프트 관리</h2>
                <button className="modal-close" onClick={() => setShowSettings(false)}>
                  ×
                </button>
              </div>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">📝 기본 프롬프트</label>
                  <textarea
                    name="prompt"
                    value={settings.prompt}
                    onChange={handleSettingsChange}
                    className="form-textarea"
                    rows="6"
                    placeholder="PDF에서 추출할 데이터 형식과 요구사항을 설명하세요...&#10;&#10;예시:&#10;- 모든 페이지에서 레미콘 거래 데이터를 추출&#10;- 공급자명과 현장명을 정확히 식별&#10;- 소계/합계 행은 제외"
                    style={{
                      minHeight: '150px',
                      fontSize: '0.9rem',
                      lineHeight: '1.5'
                    }}
                  />
                  <div style={{
                    fontSize: '0.8rem',
                    color: '#666',
                    marginTop: '0.5rem'
                  }}>
                    💡 프롬프트는 AI가 PDF 데이터를 어떻게 처리할지 결정하는 중요한 지침입니다.
                  </div>
                </div>

                <button
                  className="btn btn-success"
                  onClick={() => {
                    setShowSettings(false);
                    showNotification('프롬프트 설정이 저장되었습니다!');
                  }}
                  style={{ width: '100%' }}
                >
                  ✅ 프롬프트 저장
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Notification */}
        {notification && (
          <div className={`notification ${notification.type}`}>
            {notification.message}
          </div>
        )}
      </div>
    </>
  );
}

export default App;

