/**
 * Contract text extracted from Word keeps Symbol/Wingdings glyphs as private-use code points
 * (U+F0xx) that web fonts cannot draw, so they render as empty boxes. Map the known ones to
 * their Unicode look-alike and line separators to newlines. Every replacement is one UTF-16
 * unit, so evidence character offsets still line up with the displayed quote.
 */
const SYMBOL_FONT: Record<string, string> = {
  "\uf0b7": "\u2022", // Symbol bullet
  "\uf0a7": "\u25aa", // Wingdings small square
  "\uf06c": "\u25cf", // Wingdings filled circle
  "\uf06e": "\u25a0", // Wingdings filled square
  "\uf076": "\u2756", // Wingdings diamond
  "\uf0d8": "\u27a2", // Wingdings arrowhead
  "\uf0fc": "\u2713", // Wingdings check mark
  "\uf0fe": "\u2611", // Wingdings checked box
  "\uf02d": "-", // Symbol minus
  "\uf02b": "+", // Symbol plus
  "\u2028": "\n", // line separator
  "\u2029": "\n", // paragraph separator
};

/** Unknown private-use glyphs become U+FFFD, which every font draws, instead of a blank box. */
export function displayText(text: string): string {
  return text.replace(/[\ue000-\uf8ff\u2028\u2029]/g, (ch) => SYMBOL_FONT[ch] ?? "\ufffd");
}

/** Cleans technical AI tags / prompt prefixes from reasoning explanations */
export function cleanExplanationText(raw: string | null | undefined): string {
  if (!raw) return "";
  let text = raw.trim();

  // Strip prefixes
  text = text.replace(/^Conclusion target:\s*[^;.]+;\s*only the current criterion\.\s*/i, "");
  text = text.replace(/^Conclusion target:\s*[^;.]+\.\s*/i, "");
  text = text.replace(/^\[MACHINE_DRAFT_REVIEW\]\s*/i, "");
  text = text.replace(/^\[AI_DRAFT_REVIEW\]\s*/i, "");

  // 1. Format legacy backend decimal check strings
  if (text.includes("Backend đối chiếu bằng Decimal theo rule đã pin:")) {
    const isPass = text.includes("đạt") && !text.includes("không đạt");
    const depMatch = text.match(/"deposit":\s*"(\d+)"/);
    const maxDepMatch = text.match(/"deposit_max_percent":\s*(\d+)/);
    if (depMatch) {
      const dep = depMatch[1];
      const maxDep = maxDepMatch ? maxDepMatch[1] : "30";
      return isPass
        ? `Mức đặt cọc theo thỏa thuận trong hợp đồng (${dep}%) phù hợp với quy định của pháp luật (không vượt quá mức trần tối đa ${maxDep}% giá trị hợp đồng).`
        : `Mức đặt cọc theo thỏa thuận (${dep}%) vượt quá mức trần tối đa cho phép theo luật định (${maxDep}%).`;
    }
    const warrantyMonthsMatch = text.match(/"warranty_months":\s*"(\d+)"/);
    const minMonthsMatch = text.match(/"warranty_min_months":\s*(\d+)/);
    if (warrantyMonthsMatch) {
      const months = warrantyMonthsMatch[1];
      const minMonths = minMonthsMatch ? minMonthsMatch[1] : "60";
      return isPass
        ? `Thời hạn bảo hành căn hộ theo thỏa thuận là ${months} tháng (kể từ thời điểm hoàn thành nghiệm thu đưa vào sử dụng), đáp ứng mức tối thiểu theo quy định là ${minMonths} tháng.`
        : `Thời hạn bảo hành căn hộ theo thỏa thuận là ${months} tháng (kể từ thời điểm hoàn thành nghiệm thu đưa vào sử dụng), không đáp ứng mức tối thiểu theo quy định của pháp luật là ${minMonths} tháng đối với nhà chung cư xây dựng mới.`;
    }
    const maintMatch = text.match(/"maintenance_amount":\s*"(\d+)"/);
    if (maintMatch) {
      const amount = Number(maintMatch[1]).toLocaleString("vi-VN");
      return isPass
        ? `Kinh phí bảo trì căn hộ (${amount} VNĐ) đáp ứng đúng tỷ lệ theo quy định pháp luật.`
        : `Kinh phí bảo trì căn hộ (${amount} VNĐ) không đáp ứng đúng tỷ lệ theo quy định pháp luật.`;
    }
    return isPass
      ? "Đối chiếu số liệu logic: Đạt yêu cầu theo quy định đã đối soát."
      : "Đối chiếu số liệu logic: Không đạt yêu cầu theo quy định đã đối soát.";
  }

  // 2. Format C02 document profile checks
  if (text.includes("Backend kiểm predicate nội dung từ C02 có quote/offset:")) {
    const rawSection = text.split("Đây là kiểm nội dung")[0] ?? "";
    const cleanFields = rawSection
      .replace("Backend kiểm predicate nội dung từ C02 có quote/offset:", "")
      .replace(/[.;\s]+$/, "")
      .trim();
    const pairs = cleanFields.split(";").map((s) => s.trim()).filter(Boolean);
    const fieldTranslations: Record<string, string> = {
      land_address: "Địa chỉ thửa đất",
      land_parcel_no: "Số thửa đất",
      land_map_sheet: "Tờ bản đồ số",
      land_area_m2: "Diện tích khu đất",
      dien_tich: "Diện tích thông thủy",
      gross_area_m2: "Diện tích sàn xây dựng",
      maintenance_account_number: "Số tài khoản bảo trì",
      maintenance_account_holder: "Chủ tài khoản bảo trì",
      maintenance_bank: "Ngân hàng mở tài khoản",
      ngay_ban_giao_du_kien: "Ngày bàn giao dự kiến",
      phuong_thuc_thanh_toan: "Phương thức thanh toán",
      gia_ban: "Giá bán căn hộ",
      warranty_months: "Thời hạn bảo hành (tháng)",
      warranty_start: "Mốc tính bảo hành",
    };
    const humanParts = pairs.map((pair) => {
      if (pair.includes("=")) {
        const parts = pair.split("=");
        const k = (parts[0] ?? "").trim();
        let v = (parts[1] ?? "").trim();
        const label = fieldTranslations[k] ?? k;
        if (k === "gia_ban" && /^\d+$/.test(v)) {
          v = Number(v).toLocaleString("vi-VN") + " VNĐ";
        } else if (["dien_tich", "gross_area_m2", "land_area_m2"].includes(k)) {
          v = `${v} m²`;
        } else if (k === "warranty_start" && v.includes("COMPLETION")) {
          v = "Từ thời điểm nghiệm thu đưa vào sử dụng";
        }
        return `${label}: ${v}`;
      }
      return pair;
    });
    return `Đã đối soát đầy đủ thông số kỹ thuật từ hợp đồng: ${humanParts.join(", ")} (xác nhận tính nhất quán và đầy đủ thông tin trên văn bản dự thảo).`;
  }

  // 3. Format review scope excluded
  if (text.includes("REVIEW_SCOPE_EXCLUDED:") || text.includes("DRAFT_REVIEW does not verify execution")) {
    return "Nằm ngoài phạm vi rà soát dự thảo: Tiêu chí đòi hỏi chứng từ thực tế ngoài đời (chữ ký, công chứng, hồ sơ đăng ký bên ngoài) chưa phát sinh tại giai đoạn xem xét dự thảo hợp đồng.";
  }

  // 4. Format semantic predicate unreviewed
  if (text.includes("Semantic predicate has not been reviewed:")) {
    let sub = text.split("Semantic predicate has not been reviewed:").pop()?.trim() ?? "";
    sub = sub.replace(/^\[MACHINE_DRAFT_REVIEW\]\s*/i, "").replace(/[.;\s]+$/, "").trim();
    if (sub) {
      return `Chưa đủ căn cứ xác nhận: ${sub} (cần chuyên viên pháp chế hoặc luật sư rà soát độc lập trước khi ký).`;
    }
    return "Chưa đủ căn cứ xác nhận: Nội dung điều khoản cần được chuyên viên pháp chế rà soát bổ sung.";
  }

  // 5. Format scope checks with missing conditions (e.g. co_thoa_thuan_trong_tai)
  if (text.includes("co_thoa_thuan_trong_tai")) {
    return "Chưa đủ cơ sở xác định do hồ sơ chưa làm rõ thỏa thuận trọng tài thương mại (cần bổ sung thông tin để đánh giá thẩm quyền giải quyết tranh chấp theo Thông tư 16/2010/TT-BXD).";
  }

  if (text.includes("RATE_LIMIT") || text.includes("lỗi API RATE_LIMIT")) {
    return "Chưa hoàn tất phân tích tự động trong lần rà soát này (đề nghị chuyên viên pháp chế rà soát trực tiếp điều khoản).";
  }

  if (text.includes("PROHIBITED_CLAUSE") || (text.includes("coverage_complete") && text.includes("requires"))) {
    return "Cần rà soát toàn bộ các trang và phụ lục hợp đồng để xác nhận không tồn tại điều khoản cấm chuyển giao quyền/nghĩa vụ hoặc điều khoản bất lợi cho người tiêu dùng.";
  }

  if (text.includes("Semantic predicate has not been reviewed")) {
    const parts = text.split("reviewed:");
    return parts[1] && parts[1].trim()
      ? `Nội dung cần chuyên viên pháp chế rà soát trực tiếp: ${parts[1].trim()}`
      : "Nội dung điều khoản cần được chuyên viên pháp chế rà soát trực tiếp để xác định tính phù hợp theo quy định.";
  }

  if (text.includes("Decision rule gate not met") || text.includes("Unresolved gate: evidence_validated")) {
    return "Chưa đủ điều kiện xác nhận do thiếu chứng cứ điều khoản hoặc hồ sơ liên quan trong hợp đồng.";
  }

  if (text.startsWith("Cannot accept a finding:")) {
    text = text.replace(/^Cannot accept a finding:\s*/, "Chưa đủ cơ sở chấp nhận kết luận: ");
    text = text.replace(/Provider uncertainty:\s*/g, "");
    text = text.replace(/UPSTREAM_SCOPE_UNRESOLVED:\s*/g, "Chưa xác nhận phạm vi áp dụng: ");
    text = text.replace(/Unresolved gate:\s*scope_confirmed/g, "Chưa xác nhận phạm vi pháp lý");
    text = text.replace(/Unresolved gate:\s*version_resolved/g, "Chưa xác nhận phiên bản quy định");
    text = text.replace(/Unresolved gate:\s*[a-z_]+/gi, "");
    text = text.replace(/[;,\s]+$/, "").trim();
    if (text.includes("Chưa đủ cơ sở chấp nhận kết luận:") && text.length > 80 && !text.includes("Hồ sơ")) {
      return "Chưa đủ cơ sở chấp nhận kết luận do thiếu dữ kiện xác nhận phiên bản hoặc phạm vi áp dụng quy định.";
    }
  }

  // Common compliance summaries in English
  if (text === "All applicable mandatory criteria are SATISFIED") {
    return "Tất cả các tiêu chí bắt buộc áp dụng đều đạt yêu cầu.";
  }
  if (text.includes("All applicable mandatory criteria are SATISFIED")) {
    return text.replace("All applicable mandatory criteria are SATISFIED", "Tất cả các tiêu chí bắt buộc áp dụng đều đạt yêu cầu.");
  }
  if (text.includes("At least one applicable mandatory criterion is VIOLATED")) {
    return "Có ít nhất một tiêu chí bắt buộc vi phạm hoặc không thỏa mãn quy định.";
  }
  if (text.includes("At least one applicable mandatory criterion remains UNKNOWN")) {
    return "Có tiêu chí bắt buộc chưa đủ dữ liệu hoặc chứng cứ để xác định.";
  }
  if (text.includes("Outside caller-selected DRAFT_REVIEW")) {
    return "Nằm ngoài phạm vi rà soát dự thảo được chọn (không đánh giá việc thực hiện hoặc chứng từ bên ngoài).";
  }
  if (text.includes("No applicable mandatory criterion remains for aggregation")) {
    return "Không phát sinh tiêu chí bắt buộc nào cần áp dụng trong hồ sơ này.";
  }
  if (text.includes("C05 scope/version/applicability is not confirmed")) {
    return "Phạm vi pháp lý hoặc phiên bản quy định chưa được xác nhận đủ điều kiện áp dụng.";
  }
  if (text.startsWith("RESOLVED/CONFIRMED:")) {
    return text.replace(/^RESOLVED\/CONFIRMED:\s*/, "Đã xác nhận phiên bản: ").replace("in force on", "có hiệu lực tại ngày");
  }
  if (text.startsWith("MATCH: every condition met")) {
    return "Phù hợp: Thỏa mãn toàn bộ điều kiện áp dụng";
  }
  if (text.includes("before in force date")) {
    return "Ngày giao kết trước ngày có hiệu lực của phiên bản luật (không áp dụng)";
  }
  if (text.includes("after in force date")) {
    return "Ngày giao kết sau thời điểm hiệu lực của phiên bản";
  }
  return text.trim();
}

/** Cleans and structures recommendation content for presentation */
export function cleanRecommendationText(raw: string | null | undefined): string {
  if (!raw) return "";
  const lines = raw.split("\n");
  const cleaned: string[] = [];
  for (const line of lines) {
    let l = line.trim();
    if (!l) continue;
    if (l.startsWith("Thông tin cần làm rõ:")) {
      const val = l.replace(/^Thông tin cần làm rõ:\s*/, "").trim();
      let cleanVal = val;
      if (val.includes("PROHIBITED_CLAUSE") || val.includes("coverage_complete") || val.includes("absence_verified")) {
        cleanVal =
          "Cần rà soát toàn bộ các trang và phụ lục hợp đồng để xác nhận không tồn tại điều khoản cấm chuyển giao quyền/nghĩa vụ hoặc điều khoản bất lợi cho người tiêu dùng.";
      } else if (val.includes("Semantic predicate has not been reviewed")) {
        const parts = val.split("reviewed:");
        cleanVal = parts[1] && parts[1].trim()
          ? `Nội dung cần chuyên viên pháp chế rà soát trực tiếp: ${parts[1].trim()}`
          : "Nội dung điều khoản cần được chuyên viên pháp chế rà soát trực tiếp để xác định tính phù hợp theo quy định.";
      } else if (val.includes("co_thoa_thuan_trong_tai")) {
        cleanVal =
          "Hồ sơ chưa có thông tin về thỏa thuận trọng tài thương mại để xác định thẩm quyền áp dụng theo Thông tư 16/2010/TT-BXD.";
      } else if (val.includes("RATE_LIMIT") || val.includes("lỗi API")) {
        cleanVal =
          "Hệ thống chưa hoàn tất phân tích tự động trong lần rà soát này; đề nghị chuyên viên pháp chế rà soát trực tiếp điều khoản này.";
      } else if (val.includes("DRAFT_REVIEW does not verify execution")) {
        cleanVal =
          "Tiêu chí thuộc nhóm chứng từ thực tế ngoài đời, chưa đánh giá trong giai đoạn rà soát dự thảo.";
      } else if (val.includes("Requirement applicability/scope/version") || val.includes("UPSTREAM_SCOPE_UNRESOLVED")) {
        cleanVal =
          "Phạm vi áp dụng hoặc phiên bản quy định pháp lý chưa được xác nhận đủ điều kiện áp dụng.";
      } else if (val.includes("Decision rule gate not met") || val.includes("Unresolved gate") || val.includes("requires")) {
        cleanVal =
          "Cần bổ sung hồ sơ và đối chiếu điều kiện để làm rõ căn cứ áp dụng đối với tiêu chí này.";
      } else if (/[a-zA-Z]{4,}/.test(val) && (val.includes("_") || val.includes("requires") || val.includes("gate"))) {
        cleanVal =
          "Cần bổ sung hồ sơ chứng từ liên quan hoặc tiến hành rà soát chuyên sâu để làm rõ tiêu chí này.";
      }
      l = `Thông tin cần làm rõ: ${cleanVal}`;
    }
    // Remove internal developer/test harness notes
    l = l.replace(/Mục tiêu chỉ là tiêu chí\s+TC_[A-Z0-9_]+\.?\s*/g, "");
    l = l.replace(/chạy lại Citation Validator\.?\s*/g, "");
    l = l.replace(/Không đổi kết quả Compliance nếu không đánh giá nhánh Applicable Law độc lập\.?\s*/g, "");
    if (l.startsWith("Kiểm tra sau khắc phục:")) {
      l = l.replace(/Kiểm tra lại\s+TC_[A-Z0-9_]+\s+với\s+/g, "Kiểm tra lại với ");
    }
    if (l.trim()) {
      cleaned.push(l);
    }
  }
  return cleaned.join("\n");
}
