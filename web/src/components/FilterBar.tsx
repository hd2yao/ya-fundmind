import { Search } from "lucide-react";

export function FilterBar({
  searchLabel,
  searchValue,
  onSearchChange,
  selectLabel,
  selectValue,
  selectOptions,
  onSelectChange
}: {
  searchLabel: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  selectLabel?: string;
  selectValue?: string;
  selectOptions?: string[];
  onSelectChange?: (value: string) => void;
}) {
  return (
    <div className="filter-bar">
      <label className="search-control">
        <Search size={17} aria-hidden />
        <span className="sr-only">{searchLabel}</span>
        <input
          type="search"
          aria-label={searchLabel}
          placeholder={searchLabel}
          value={searchValue}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </label>
      {selectLabel && selectOptions && onSelectChange ? (
        <label className="select-control">
          <span>{selectLabel}</span>
          <select aria-label={selectLabel} value={selectValue} onChange={(event) => onSelectChange(event.target.value)}>
            {selectOptions.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
      ) : null}
    </div>
  );
}
